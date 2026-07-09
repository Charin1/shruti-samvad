from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, desc
from typing import List, Optional
from uuid import UUID

from core.database.session import get_session
from core.database.models.article import Article, ArticleRead, ArticleSave, ArticleStar

router = APIRouter()

@router.get("/", response_model=List[Article])
async def list_articles(
    feed_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    session = Depends(get_session)
):
    """List articles with optional feed filtering and pagination."""
    query = select(Article).order_by(desc(Article.published_at))
    
    if feed_id:
        query = query.where(Article.feed_id == feed_id)
        
    query = query.limit(limit).offset(offset)
    
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/{article_id}", response_model=Article)
async def get_article(article_id: UUID, session = Depends(get_session)):
    """Get content of a specific article."""
    article = await session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("/{article_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_as_read(article_id: UUID, user_id: UUID, session = Depends(get_session)):
    """Mark an article as read."""
    # Check if exists
    article = await session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Create or update ArticleRead
    read_entry = await session.get(ArticleRead, (user_id, article_id))
    if not read_entry:
        read_entry = ArticleRead(user_id=user_id, article_id=article_id)
        session.add(read_entry)
        await session.commit()
    
    return None

@router.post("/{article_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def save_article(article_id: UUID, user_id: UUID, session = Depends(get_session)):
    """Save an article for later."""
    save_entry = ArticleSave(user_id=user_id, article_id=article_id)
    session.add(save_entry)
    await session.commit()
    return None

@router.post("/{article_id}/star", status_code=status.HTTP_204_NO_CONTENT)
async def star_article(article_id: UUID, user_id: UUID, session = Depends(get_session)):
    """Star an article."""
    star_entry = ArticleStar(user_id=user_id, article_id=article_id)
    session.add(star_entry)
    await session.commit()
    return None
