from uuid import UUID, uuid4
from typing import Optional
from sqlmodel import SQLModel, Field

class Rule(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    name: str
    condition_type: str
    condition_value: str
    action: str
    action_value: Optional[str] = None
    is_active: bool = Field(default=True)
