import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.memory import MemoryRead
from app.services import memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryRead])
def list_memories(
    category: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemoryRead]:
    """Lets the user see exactly what Ram has stored about them — required
    for the product's transparency/user-control commitment, not just an
    admin debug view."""
    return memory_service.list_memories(db, current_user.id, category=category)


@router.post("/{memory_id}/archive", response_model=MemoryRead)
def archive_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryRead:
    try:
        return memory_service.archive_memory(db, current_user.id, memory_id)
    except memory_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        memory_service.delete_memory(db, current_user.id, memory_id)
    except memory_service.NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
