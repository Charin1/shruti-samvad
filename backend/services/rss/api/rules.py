from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from typing import List
from uuid import UUID

from core.database.session import get_session
from core.database.models.rule import Rule

router = APIRouter()

@router.get("/", response_model=List[Rule])
async def list_rules(user_id: UUID, session = Depends(get_session)):
    """List all active rules for a user."""
    query = select(Rule).where(Rule.user_id == user_id)
    result = await session.execute(query)
    return result.scalars().all()

@router.post("/", response_model=Rule, status_code=status.HTTP_201_CREATED)
async def create_rule(rule: Rule, session = Depends(get_session)):
    """Create a new automation rule."""
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: UUID, session = Depends(get_session)):
    """Remove a rule."""
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await session.delete(rule)
    await session.commit()
    return None

@router.patch("/{rule_id}", response_model=Rule)
async def update_rule(rule_id: UUID, rule_update: dict, session = Depends(get_session)):
    """Toggle or update a rule."""
    rule = await session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    for key, value in rule_update.items():
        setattr(rule, key, value)
    
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule
