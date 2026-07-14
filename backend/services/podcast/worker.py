import asyncio
import json
import os
from datetime import datetime
from typing import Optional
from arq.connections import RedisSettings
from sqlmodel import select
from uuid import UUID

from core.database.session import async_session_maker
from core.database.models import Article, Episode, EpisodeArticle, JobStatus
from services.podcast.agent.graph import get_episode_graph
from services.podcast.services.estimator import STAGE_ORDER, estimate_progress

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PODCAST_QUEUE = "arq:podcast"
PROGRESS_TICK_SECONDS = float(os.getenv("PROGRESS_TICK_SECONDS", "5"))


async def _publish(ctx, episode_id: str, status: str, **extra):
    payload = json.dumps({"job_id": episode_id, "status": status, **extra})
    await ctx["redis"].publish(f"job_status_{episode_id}", payload)


class _ProgressTicker:
    """
    Periodically re-publishes an elapsed-time-based progress estimate while a
    single node (typically a multi-minute LLM call) is running — the graph
    only yields events between node completions, so without this there would
    be zero feedback for the whole duration of e.g. the summarize/script
    steps. Synthesizing is excluded: tts_node already publishes real
    chunk-level progress via its own on_progress callback.
    """

    def __init__(self, ctx, episode_id: str, article_count: int, target_minutes: float):
        self._ctx = ctx
        self._episode_id = episode_id
        self._article_count = article_count
        self._target_minutes = target_minutes
        self._current_stage: Optional[str] = None
        self._stage_entered_at = datetime.utcnow()
        self._task: Optional[asyncio.Task] = None

    def set_stage(self, status: str) -> None:
        if status != self._current_stage:
            self._current_stage = status
            self._stage_entered_at = datetime.utcnow()

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(PROGRESS_TICK_SECONDS)
            if self._current_stage in STAGE_ORDER and self._current_stage != "synthesizing":
                elapsed = (datetime.utcnow() - self._stage_entered_at).total_seconds()
                progress, eta_seconds = estimate_progress(
                    self._current_stage, elapsed, self._article_count, self._target_minutes
                )
                await _publish(self._ctx, self._episode_id, self._current_stage, progress=progress, eta_seconds=eta_seconds)

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()


async def _load_episode_articles(session, episode_id: UUID):
    """Ordered (EpisodeArticle, Article) rows for an episode, position ascending."""
    result = await session.execute(
        select(EpisodeArticle, Article)
        .join(Article, EpisodeArticle.article_id == Article.id)
        .where(EpisodeArticle.episode_id == episode_id)
        .order_by(EpisodeArticle.position)
    )
    return result.all()


async def _stream_and_persist(ctx, session, episode: Episode, graph, config, resume_input, article_count: int) -> None:
    """
    Drive the graph (fresh run or resume) and persist each streamed delta to
    the Episode row + Redis status channel — shared between a first run and a
    review-resume, since both need identical per-event handling.
    """
    episode_id = str(episode.id)
    ticker = _ProgressTicker(ctx, episode_id, article_count, episode.target_minutes)
    ticker.start()

    try:
        async for event in graph.astream(resume_input, config=config):
            node_name = next(iter(event))
            state_update = event[node_name]

            if not isinstance(state_update, dict):
                continue

            for article_summary in state_update.get("article_summaries") or []:
                if article_summary.get("summary"):
                    ea = (
                        await session.execute(
                            select(EpisodeArticle).where(
                                EpisodeArticle.episode_id == episode.id,
                                EpisodeArticle.article_id == UUID(article_summary["article_id"]),
                            )
                        )
                    ).scalars().first()
                    if ea:
                        ea.summary = article_summary["summary"]
                        session.add(ea)

            if state_update.get("summary"):
                episode.summary = state_update["summary"]
            if state_update.get("podcast_script"):
                episode.podcast_script = state_update["podcast_script"]

            new_status = state_update.get("status")
            if new_status:
                try:
                    episode.status = JobStatus(new_status)
                except ValueError:
                    pass
                if new_status == "error" and state_update.get("error"):
                    episode.error_message = state_update["error"]
                session.add(episode)
                await session.commit()

                ticker.set_stage(new_status)
                # Publish an immediate estimate alongside the transition itself
                # (elapsed=0 in the new stage) so the UI updates right away
                # instead of waiting up to PROGRESS_TICK_SECONDS for the first
                # tick — the ticker keeps it moving for the rest of the stage.
                # Synthesizing is excluded: tts_node publishes real progress.
                extra = {}
                if new_status in STAGE_ORDER and new_status != "synthesizing":
                    progress, eta_seconds = estimate_progress(new_status, 0, article_count, episode.target_minutes)
                    extra = {"progress": progress, "eta_seconds": eta_seconds}
                await _publish(ctx, episode_id, new_status, **extra)

            if state_update.get("audio_path"):
                episode.audio_file_path = state_update["audio_path"]
                session.add(episode)
                await session.commit()
    finally:
        ticker.stop()

    # The graph either reached END or paused at the review interrupt —
    # `.next` tells us which, since a paused run's last event already set
    # status="awaiting_review" but didn't reach a terminal state.
    snapshot = await graph.aget_state(config)
    if not snapshot.next and episode.status != JobStatus.error:
        episode.status = JobStatus.done
        session.add(episode)
        await session.commit()
        await _publish(ctx, episode_id, "done", progress=100, eta_seconds=0)


async def process_episode_job(ctx, episode_id: UUID):
    async with async_session_maker() as session:
        episode = await session.get(Episode, episode_id)
        if not episode:
            return f"Episode {episode_id} not found"

        rows = await _load_episode_articles(session, episode.id)
        articles_input = [
            {
                "article_id": str(ea.article_id),
                "clean_text": article.clean_text or article.raw_html,
                "position": ea.position,
            }
            for ea, article in rows
            if article and (article.clean_text or article.raw_html)
        ]

        if not articles_input:
            episode.status = JobStatus.error
            episode.error_message = "No article in this episode has extractable text."
            session.add(episode)
            await session.commit()
            await _publish(ctx, str(episode.id), "error", error=episode.error_message)
            return episode.error_message

        graph = await get_episode_graph()
        config = {"configurable": {"thread_id": str(episode.id)}}

        snapshot = await graph.aget_state(config)
        if snapshot.next:
            # A prior run for this episode was interrupted or crashed mid-flight —
            # resume from the checkpoint instead of restarting from scratch.
            resume_input = None
            print(f"Resuming episode {episode.id} from checkpoint (pending: {snapshot.next})")
        else:
            resume_input = {
                "episode_id": str(episode.id),
                "target_minutes": episode.target_minutes,
                "review_requested": episode.review_requested,
                "voice": episode.voice,
                "voice_cohost": episode.voice_cohost,
                "podcast_format": episode.podcast_format,
                "podcast_style": episode.podcast_style,
                "custom_prompt": episode.custom_prompt,
                "bg_music": episode.bg_music,
                "articles": articles_input,
                "article_summaries": [],
                "summary": "",
                "podcast_script": "",
                "audio_path": None,
                "status": "summarizing",
                "error": None,
            }
            episode.status = JobStatus.summarizing
            episode.error_message = None
            session.add(episode)
            await session.commit()
            await _publish(ctx, str(episode.id), "summarizing")
            print(f"Starting episode {episode.id} ({len(articles_input)} article(s))")

        try:
            await _stream_and_persist(ctx, session, episode, graph, config, resume_input, len(articles_input))
            return f"Episode {episode.id} processed (status={episode.status})"
        except BaseException as e:
            err = "Job cancelled (timeout)" if isinstance(e, asyncio.CancelledError) else str(e)
            episode.status = JobStatus.error
            episode.error_message = err
            session.add(episode)
            await session.commit()
            await _publish(ctx, str(episode.id), "error", error=err)
            if isinstance(e, asyncio.CancelledError):
                raise
            return f"Error processing episode {episode.id}: {e}"


async def resume_episode_job(ctx, episode_id: UUID, edited_script: Optional[str] = None):
    """Resume an episode paused at the review gate, optionally with a human-edited script."""
    async with async_session_maker() as session:
        episode = await session.get(Episode, episode_id)
        if not episode:
            return f"Episode {episode_id} not found"

        graph = await get_episode_graph()
        config = {"configurable": {"thread_id": str(episode.id)}}

        snapshot = await graph.aget_state(config)
        if not snapshot.next:
            return f"Episode {episode.id} has no paused checkpoint to resume from"

        if edited_script:
            await graph.aupdate_state(config, {"podcast_script": edited_script})
            episode.podcast_script = edited_script

        episode.status = JobStatus.synthesizing
        session.add(episode)
        await session.commit()
        await _publish(ctx, str(episode.id), "synthesizing")

        rows = await _load_episode_articles(session, episode.id)

        try:
            await _stream_and_persist(ctx, session, episode, graph, config, None, len(rows))
            return f"Episode {episode.id} resumed and processed (status={episode.status})"
        except BaseException as e:
            err = "Job cancelled (timeout)" if isinstance(e, asyncio.CancelledError) else str(e)
            episode.status = JobStatus.error
            episode.error_message = err
            session.add(episode)
            await session.commit()
            await _publish(ctx, str(episode.id), "error", error=err)
            if isinstance(e, asyncio.CancelledError):
                raise
            return f"Error resuming episode {episode.id}: {e}"


async def on_startup(ctx):
    """
    Verify TTS assets and warm up the episode graph (which initializes the
    checkpointer file/tables) as soon as the worker boots, so a missing model
    or checkpointer setup problem is a loud, immediate signal rather than a
    failure discovered minutes into a job. Non-fatal for the TTS check: keeps
    the worker usable for jobs that only need to reach the scripting stage
    during setup/dev.
    """
    from services.podcast.services.tts import tts_service, TTSAssetsMissing
    try:
        tts_service.ensure_ready()
        print("[podcast worker] TTS assets verified OK.")
    except TTSAssetsMissing as e:
        print(f"[podcast worker] WARNING: {e} — TTS jobs will fail until this is fixed.")

    await get_episode_graph()
    print("[podcast worker] Episode graph + checkpointer initialized.")


class WorkerSettings:
    functions = [process_episode_job, resume_episode_job]
    on_startup = on_startup
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    queue_name = PODCAST_QUEUE
    job_timeout = 1800  # 30 min — LLM + TTS can take several minutes
