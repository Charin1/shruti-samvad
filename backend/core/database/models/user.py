from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    external_id: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Workspace(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    owner_id: UUID = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorkspaceMember(SQLModel, table=True):
    workspace_id: UUID = Field(foreign_key="workspace.id", primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    role: str = Field(default="member")
    joined_at: datetime = Field(default_factory=datetime.utcnow)
