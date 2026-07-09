from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from typing import List
from uuid import UUID

from core.database.session import get_session
from core.database.models.board import Board, BoardItem, BoardMember

router = APIRouter()

@router.get("/", response_model=List[Board])
async def list_boards(user_id: UUID, session = Depends(get_session)):
    """List all boards a user belongs to."""
    # This involves joining with BoardMember
    query = (
        select(Board)
        .join(BoardMember)
        .where(BoardMember.user_id == user_id)
    )
    result = await session.execute(query)
    return result.scalars().all()

@router.post("/", response_model=Board, status_code=status.HTTP_201_CREATED)
async def create_board(board: Board, session = Depends(get_session)):
    """Create a new board."""
    session.add(board)
    
    # Auto-add creator as owner/admin
    member = BoardMember(board_id=board.id, user_id=board.user_id, role="owner")
    session.add(member)
    
    await session.commit()
    await session.refresh(board)
    return board

@router.post("/{board_id}/items", status_code=status.HTTP_201_CREATED)
async def add_to_board(board_id: UUID, item: BoardItem, session = Depends(get_session)):
    """Add an article to a board."""
    session.add(item)
    await session.commit()
    return {"message": "Added to board"}

@router.get("/{board_id}/items")
async def list_board_items(board_id: UUID, session = Depends(get_session)):
    """List all items in a board."""
    query = select(BoardItem).where(BoardItem.board_id == board_id)
    result = await session.execute(query)
    return result.scalars().all()
