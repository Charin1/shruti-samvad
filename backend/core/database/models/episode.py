from enum import Enum
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    fetching = "fetching"
    summarizing = "summarizing"
    scripting = "scripting"
    awaiting_review = "awaiting_review"
    synthesizing = "synthesizing"
    saving = "saving"
    done = "done"
    error = "error"


class Episode(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: Optional[str] = None
    status: JobStatus = Field(default=JobStatus.pending)
    review_requested: bool = Field(default=False)
    target_minutes: float = Field(default=3.0)
    summary: Optional[str] = None
    podcast_script: Optional[str] = None
    audio_file_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EpisodeArticle(SQLModel, table=True):
    episode_id: UUID = Field(foreign_key="episode.id", primary_key=True)
    article_id: UUID = Field(foreign_key="article.id", primary_key=True)
    position: int = Field(default=0)
    summary: Optional[str] = None
