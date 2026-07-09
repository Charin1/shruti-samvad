from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field

class Board(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BoardItem(SQLModel, table=True):
    board_id: UUID = Field(foreign_key="board.id", primary_key=True)
    article_id: UUID = Field(foreign_key="article.id", primary_key=True)
    added_by: UUID = Field(index=True)
    added_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = None

class BoardMember(SQLModel, table=True):
    board_id: UUID = Field(foreign_key="board.id", primary_key=True)
    user_id: UUID = Field(primary_key=True)
    role: str = Field(default="viewer")
    joined_at: datetime = Field(default_factory=datetime.utcnow)
