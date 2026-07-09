from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from .feed import Feed

class Article(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    feed_id: UUID = Field(foreign_key="feed.id", index=True)
    title: str
    url: str = Field(index=True)
    raw_html: Optional[str] = None
    clean_text: Optional[str] = None
    published_at: datetime = Field(index=True)
    content_hash: str = Field(index=True)
    is_duplicate: bool = Field(default=False)

    # Relationships
    feed: "Feed" = Relationship(back_populates="articles")

class ArticleRead(SQLModel, table=True):
    user_id: UUID = Field(primary_key=True)
    article_id: UUID = Field(foreign_key="article.id", primary_key=True)
    read_at: datetime = Field(default_factory=datetime.utcnow)

class ArticleSave(SQLModel, table=True):
    user_id: UUID = Field(primary_key=True)
    article_id: UUID = Field(foreign_key="article.id", primary_key=True)
    saved_at: datetime = Field(default_factory=datetime.utcnow)

class ArticleStar(SQLModel, table=True):
    user_id: UUID = Field(primary_key=True)
    article_id: UUID = Field(foreign_key="article.id", primary_key=True)
    starred_at: datetime = Field(default_factory=datetime.utcnow)
