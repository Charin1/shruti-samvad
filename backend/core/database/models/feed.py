from datetime import datetime
from uuid import UUID, uuid4
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship

class Feed(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    favicon_url: Optional[str] = None
    language: Optional[str] = None
    update_frequency_minutes: int = Field(default=60)
    last_fetched_at: Optional[datetime] = None

    # Relationships
    folder_maps: List["FeedFolderMap"] = Relationship(back_populates="feed")
    articles: List["Article"] = Relationship(back_populates="feed")

class Folder(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    user_id: UUID = Field(index=True)

    # Relationships
    feed_maps: List["FeedFolderMap"] = Relationship(back_populates="folder")

class Tag(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    user_id: UUID = Field(index=True)

class FeedFolderMap(SQLModel, table=True):
    feed_id: UUID = Field(foreign_key="feed.id", primary_key=True)
    folder_id: UUID = Field(foreign_key="folder.id", primary_key=True)
    user_id: UUID = Field(index=True)

    # Relationships
    feed: Feed = Relationship(back_populates="folder_maps")
    folder: Folder = Relationship(back_populates="feed_maps")
