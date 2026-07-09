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


class CreateEpisodeRequest(BaseModel):
    article_ids: List[UUID]
    title: Optional[str] = None
    target_minutes: float = 3.0
    review_requested: bool = False


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
    """Create an episode from 1..N articles and enqueue generation.

    Every call creates a new episode row (no in-place regeneration) — clicking
    "Generate" again produces a new library entry rather than overwriting one,
    which keeps prior attempts visible.
    """
    if not payload.article_ids:
        raise HTTPException(status_code=400, detail="At least one article_id is required")

    episode = Episode(
        title=payload.title,
        target_minutes=payload.target_minutes,
        review_requested=payload.review_requested,
        status=JobStatus.pending,
    )
    session.add(episode)
    await session.commit()
    await session.refresh(episode)

    for position, article_id in enumerate(payload.article_ids):
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
