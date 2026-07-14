from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
import asyncio
import redis.asyncio as aioredis
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import json
from typing import Dict, List, Optional, Set
from uuid import UUID
from datetime import datetime

from sqlmodel import select, desc
from pydantic import BaseModel

from core.database.session import get_session
from core.database.models import Episode, EpisodeArticle, JobStatus, Article
from arq import create_pool
from arq.connections import RedisSettings

_arq_pool = None


async def get_arq_pool():
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(RedisSettings.from_dsn(redis_url))
    return _arq_pool

app = FastAPI(
    title="Shruti Samvad Podcast API",
    description="API for AI podcast generation and status streaming",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Subscriber registry for WebSockets: {episode_id: {websocket_connections}}
subscribers: Dict[str, Set[WebSocket]] = {}
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def redis_listener():
    """Background task to listen for job status updates on Redis and broadcast them."""
    redis = await aioredis.from_url(redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.psubscribe("job_status_*")

    try:
        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                channel = message['channel']
                episode_id = channel.replace("job_status_", "")
                data = json.loads(message['data'])
                await broadcast_status(episode_id, data)
    except Exception as e:
        print(f"Redis listener error: {e}")

@app.on_event("startup")
async def startup_event():
    # Start the redis listener in the background
    asyncio.create_task(redis_listener())

@app.get("/")
async def root():
    return {"message": "Shruti Samvad Podcast API is running"}

@app.get("/voices")
async def get_voices():
    """List available TTS voices from Kokoro model."""
    from services.podcast.services.tts import tts_service
    try:
        voices = tts_service.get_voices()
        return {"voices": voices}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS not ready: {str(e)}")

@app.get("/voices/{voice_name}/preview")
async def get_voice_preview(voice_name: str):
    """Generate or retrieve a short voice preview audio clip."""
    from services.podcast.services.tts import tts_service
    from pydub import AudioSegment
    from fastapi.responses import FileResponse
    import os

    try:
        available_voices = tts_service.get_voices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS not ready: {str(e)}")

    if voice_name not in available_voices:
        raise HTTPException(status_code=404, detail=f"Voice {voice_name} not found")

    preview_dir = os.path.join(AUDIO_STORAGE_PATH, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    final_mp3_path = os.path.join(preview_dir, f"{voice_name}.mp3")

    if not os.path.exists(final_mp3_path):
        spoken_voice_name = voice_name.replace("_", " ")
        text = f"Hello! This is a preview of the {spoken_voice_name} voice in Shruti Samvad. I hope I sound suitable for your podcast."
        temp_wav_path = os.path.join(preview_dir, f"{voice_name}.wav")
        try:
            await tts_service.synthesize(text, temp_wav_path, voice=voice_name)
            audio = AudioSegment.from_wav(temp_wav_path)
            audio.export(final_mp3_path, format="mp3", bitrate="128k")
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
        except Exception as e:
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
            raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

    return FileResponse(final_mp3_path, media_type="audio/mpeg")

@app.websocket("/ws/{episode_id}")
async def job_status_ws(websocket: WebSocket, episode_id: str):
    await websocket.accept()
    if episode_id not in subscribers:
        subscribers[episode_id] = set()
    subscribers[episode_id].add(websocket)

    try:
        while True:
            # Keep the connection open and wait for messages (though usually client just listens)
            data = await websocket.receive_text()
            # Handle potential subscription messages if needed
    except WebSocketDisconnect:
        subscribers[episode_id].remove(websocket)
        if not subscribers[episode_id]:
            del subscribers[episode_id]

async def broadcast_status(episode_id: str, status: dict):
    """Utility to push status updates to all WebSocket subscribers for an episode."""
    if episode_id in subscribers:
        message = json.dumps(status)
        for ws in subscribers[episode_id]:
            try:
                await ws.send_text(message)
            except Exception:
                pass

# Mount audio storage
AUDIO_STORAGE_PATH = os.getenv("AUDIO_STORAGE_PATH", "./storage/audio")
os.makedirs(AUDIO_STORAGE_PATH, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_STORAGE_PATH), name="audio")


class EpisodeOut(BaseModel):
    id: str
    title: Optional[str]
    status: str
    review_requested: bool
    article_count: int
    article_titles: List[str]
    audio_file_path: Optional[str]
    error_message: Optional[str]
    voice: str
    voice_cohost: str
    podcast_format: str
    podcast_style: str
    custom_prompt: Optional[str]
    bg_music: bool
    created_at: datetime

    class Config:
        from_attributes = True


class EpisodeArticleOut(BaseModel):
    article_id: str
    title: str
    position: int
    summary: Optional[str]


class EpisodeDetailOut(EpisodeOut):
    summary: Optional[str]
    podcast_script: Optional[str]
    target_minutes: float
    articles: List[EpisodeArticleOut]


class CustomArticleRequest(BaseModel):
    title: str
    content: str


class CreateEpisodeRequest(BaseModel):
    article_ids: List[UUID] = []
    custom_articles: Optional[List[CustomArticleRequest]] = None
    title: Optional[str] = None
    target_minutes: float = 3.0
    review_requested: bool = False
    voice: str = "af_heart"  # TTS voice selection
    voice_cohost: str = "af_sky"  # Co-host TTS voice selection
    podcast_format: str = "monologue"  # monologue or dialogue
    podcast_style: str = "conversational"
    custom_prompt: Optional[str] = None
    bg_music: bool = False


class ReviewScriptRequest(BaseModel):
    script: str


async def _episode_articles(session, episode_id: UUID):
    result = await session.execute(
        select(EpisodeArticle, Article)
        .join(Article, EpisodeArticle.article_id == Article.id)
        .where(EpisodeArticle.episode_id == episode_id)
        .order_by(EpisodeArticle.position)
    )
    return result.all()


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)


async def _episode_to_out(session, episode: Episode) -> EpisodeOut:
    pairs = await _episode_articles(session, episode.id)
    return EpisodeOut(
        id=str(episode.id),
        title=episode.title,
        status=_status_value(episode.status),
        review_requested=episode.review_requested,
        article_count=len(pairs),
        article_titles=[article.title for _, article in pairs],
        audio_file_path=episode.audio_file_path,
        error_message=episode.error_message,
        voice=episode.voice,
        voice_cohost=episode.voice_cohost,
        podcast_format=episode.podcast_format,
        podcast_style=episode.podcast_style,
        custom_prompt=episode.custom_prompt,
        bg_music=episode.bg_music,
        created_at=episode.created_at,
    )


@app.get("/episodes", response_model=List[EpisodeOut])
async def list_episodes(session=Depends(get_session)):
    """List all episodes ordered by most recent."""
    result = await session.execute(select(Episode).order_by(desc(Episode.created_at)))
    episodes = result.scalars().all()
    return [await _episode_to_out(session, episode) for episode in episodes]


@app.get("/episodes/{episode_id}", response_model=EpisodeDetailOut)
async def get_episode(episode_id: UUID, session=Depends(get_session)):
    episode = await session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    pairs = await _episode_articles(session, episode.id)
    base = await _episode_to_out(session, episode)
    return EpisodeDetailOut(
        **base.model_dump(),
        summary=episode.summary,
        podcast_script=episode.podcast_script,
        target_minutes=episode.target_minutes,
        articles=[
            EpisodeArticleOut(
                article_id=str(ea.article_id),
                title=article.title,
                position=ea.position,
                summary=ea.summary,
            )
            for ea, article in pairs
        ],
    )


@app.post("/episodes", status_code=201)
async def create_episode(payload: CreateEpisodeRequest, session=Depends(get_session)):
    """Create an episode from 1..N articles and enqueue generation."""
    if not payload.article_ids and not payload.custom_articles:
        raise HTTPException(status_code=400, detail="At least one article_id or custom_article is required")

    article_ids = list(payload.article_ids)

    # Save custom pasted articles to the database under a system feed
    if payload.custom_articles:
        import uuid
        import hashlib
        from core.database.models import Feed, Article

        # Get or create pasted feed
        result = await session.execute(select(Feed).where(Feed.url == "system://custom-pasted-content"))
        feed = result.scalars().first()
        if not feed:
            feed = Feed(
                id=uuid.uuid4(),
                url="system://custom-pasted-content",
                title="Pasted Blog Content",
                favicon_url=None,
                language="en",
                update_frequency_minutes=999999,
                last_fetched_at=datetime.utcnow()
            )
            session.add(feed)
            await session.commit()
            await session.refresh(feed)

        # Create and save Article rows
        for custom_art in payload.custom_articles:
            art_id = uuid.uuid4()
            content_hash = hashlib.sha256(custom_art.content.encode('utf-8')).hexdigest()

            article = Article(
                id=art_id,
                feed_id=feed.id,
                title=custom_art.title.strip() or "Pasted Article",
                url=f"system://custom-pasted-content/{art_id}",
                raw_html=None,
                clean_text=custom_art.content,
                published_at=datetime.utcnow(),
                content_hash=content_hash,
                is_duplicate=False
            )
            session.add(article)
            article_ids.append(art_id)

        await session.commit()

    episode = Episode(
        title=payload.title,
        target_minutes=payload.target_minutes,
        review_requested=payload.review_requested,
        voice=payload.voice,
        voice_cohost=payload.voice_cohost,
        podcast_format=payload.podcast_format,
        podcast_style=payload.podcast_style,
        custom_prompt=payload.custom_prompt,
        bg_music=payload.bg_music,
        status=JobStatus.pending,
    )
    session.add(episode)
    await session.commit()
    await session.refresh(episode)

    for position, article_id in enumerate(article_ids):
        session.add(EpisodeArticle(episode_id=episode.id, article_id=article_id, position=position))
    await session.commit()

    pool = await get_arq_pool()
    await pool.enqueue_job("process_episode_job", episode.id, _queue_name="arq:podcast")
    return {"episode_id": str(episode.id), "status": "queued"}


@app.post("/episodes/{episode_id}/review")
async def submit_script_review(episode_id: UUID, payload: ReviewScriptRequest, session=Depends(get_session)):
    """Approve (optionally edited) script for an episode paused at the review gate."""
    episode = await session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    if episode.status != JobStatus.awaiting_review:
        raise HTTPException(
            status_code=409,
            detail=f"Episode is not awaiting review (status={_status_value(episode.status)})",
        )

    pool = await get_arq_pool()
    await pool.enqueue_job("resume_episode_job", episode.id, payload.script, _queue_name="arq:podcast")
    return {"episode_id": str(episode.id), "status": "queued"}


class TTSPreviewRequest(BaseModel):
    text: str
    voice: str = "af_heart"


@app.post("/tts/preview")
async def get_custom_tts_preview(payload: TTSPreviewRequest):
    """Generate or retrieve a short custom TTS preview audio clip."""
    from services.podcast.services.tts import tts_service
    from pydub import AudioSegment
    from fastapi.responses import FileResponse
    import hashlib
    import os

    try:
        available_voices = tts_service.get_voices()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS not ready: {str(e)}")

    if payload.voice not in available_voices:
        raise HTTPException(status_code=404, detail=f"Voice {payload.voice} not found")

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text snippet cannot be empty")

    preview_dir = os.path.join(AUDIO_STORAGE_PATH, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    
    # Calculate SHA256 of voice + text to cache generated snippet audio
    cache_key = hashlib.sha256(f"{payload.voice}:{payload.text.strip()}".encode("utf-8")).hexdigest()
    final_mp3_path = os.path.join(preview_dir, f"custom_{cache_key}.mp3")

    if not os.path.exists(final_mp3_path):
        temp_wav_path = os.path.join(preview_dir, f"custom_{cache_key}.wav")
        try:
            await tts_service.synthesize(payload.text.strip(), temp_wav_path, voice=payload.voice)
            audio = AudioSegment.from_wav(temp_wav_path)
            audio.export(final_mp3_path, format="mp3", bitrate="128k")
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
        except Exception as e:
            if os.path.exists(temp_wav_path):
                os.remove(temp_wav_path)
            raise HTTPException(status_code=500, detail=f"Failed to generate custom preview: {str(e)}")

    return FileResponse(final_mp3_path, media_type="audio/mpeg")
