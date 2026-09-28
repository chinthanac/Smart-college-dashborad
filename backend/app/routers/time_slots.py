from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user, get_current_user
from app.models.user import User
from app.schemas.time_slot import TimeSlotCreate, TimeSlotOut, TimeSlotUpdate
from app.services import time_slot_service

router = APIRouter()


@router.get("", response_model=list[TimeSlotOut])
def list_time_slots(
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Readable by every role — students and faculty need the period times to
    render their own timetable."""
    records = time_slot_service.list_time_slots(db, is_active=is_active)
    return [time_slot_service.serialize(item) for item in records]


@router.get("/", response_model=list[TimeSlotOut])
def list_time_slots_root(
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_time_slots(is_active=is_active, db=db, current_user=current_user)


@router.post("", response_model=TimeSlotOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TimeSlotOut, status_code=status.HTTP_201_CREATED)
def create_time_slot(
    payload: TimeSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    slot = time_slot_service.create_time_slot(db, payload)
    return time_slot_service.serialize(slot)


@router.get("/{slot_id}", response_model=TimeSlotOut)
def get_time_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return time_slot_service.serialize(time_slot_service.get_time_slot_or_404(db, slot_id))


@router.put("/{slot_id}", response_model=TimeSlotOut)
def update_time_slot(
    slot_id: int,
    payload: TimeSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    slot = time_slot_service.get_time_slot_or_404(db, slot_id)
    return time_slot_service.serialize(time_slot_service.update_time_slot(db, slot, payload))


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_time_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    slot = time_slot_service.get_time_slot_or_404(db, slot_id)
    time_slot_service.delete_time_slot(db, slot)
    return None
