from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from core.database.session import get_session
from core.database.models.feed import Feed
from services.rss.api.queue import get_arq_pool

router = APIRouter()


class FeedUpdate(BaseModel):
    title: Optional[str] = None
    url: Optional[str] = None
    update_frequency_minutes: Optional[int] = None

@router.get("/", response_model=List[Feed])
async def list_feeds(session = Depends(get_session)):
    """List all RSS feeds."""
    feeds = await session.execute(select(Feed))
    return feeds.scalars().all()

@router.post("/", response_model=Feed, status_code=status.HTTP_201_CREATED)
async def create_feed(feed: Feed, session = Depends(get_session)):
    """Add a new RSS feed. URL must be unique."""
    # Check if feed already exists
    existing = await session.execute(select(Feed).where(Feed.url == feed.url))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Feed with this URL already exists")
    
    session.add(feed)
    await session.commit()
    await session.refresh(feed)

    # Trigger an initial fetch so articles start populating immediately.
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("fetch_feed_task", feed.id)
    except Exception as e:
        # Don't fail feed creation if the queue is unavailable.
        print(f"Could not enqueue initial fetch for {feed.url}: {e}")

    return feed

@router.get("/{feed_id}", response_model=Feed)
async def get_feed(feed_id: UUID, session = Depends(get_session)):
    """Get details of a specific feed."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    return feed

@router.patch("/{feed_id}", response_model=Feed)
async def update_feed(feed_id: UUID, data: FeedUpdate, session = Depends(get_session)):
    """Update feed title, URL, or refresh interval."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    if data.title is not None:
        feed.title = data.title
    if data.url is not None:
        # Check uniqueness of new URL (unless it's the same as current)
        if data.url != feed.url:
            existing = await session.execute(select(Feed).where(Feed.url == data.url))
            if existing.scalars().first():
                raise HTTPException(status_code=400, detail="Feed with this URL already exists")
        feed.url = data.url
    if data.update_frequency_minutes is not None:
        feed.update_frequency_minutes = data.update_frequency_minutes

    session.add(feed)
    await session.commit()
    await session.refresh(feed)
    return feed


@router.post("/{feed_id}/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_feed(feed_id: UUID, session = Depends(get_session)):
    """Manually trigger a fetch for a feed."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("fetch_feed_task", feed.id)
    except Exception as e:
        print(f"Could not enqueue refresh for {feed.id}: {e}")
        raise HTTPException(status_code=503, detail="Queue unavailable — worker may not be running")

    return {"status": "queued", "feed_id": str(feed.id)}


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(feed_id: UUID, session = Depends(get_session)):
    """Remove a feed."""
    feed = await session.get(Feed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    await session.delete(feed)
    await session.commit()
    return None
