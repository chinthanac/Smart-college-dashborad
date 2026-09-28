"""The college bell schedule.

Small on purpose: the timetable module leans on these rows for every clash
check, so the one rule worth enforcing here is that periods may not overlap
each other.
"""

from datetime import time

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.schemas.time_slot import TimeSlotCreate, TimeSlotOut, TimeSlotUpdate

DUPLICATE_PERIOD_DETAIL = (
    "A period with this number already exists. Edit that period instead of adding a second one."
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


def _hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def serialize(slot: TimeSlot) -> TimeSlotOut:
    return TimeSlotOut(
        id=slot.id,
        period_number=slot.period_number,
        name=slot.name,
        start_time=slot.start_time,
        end_time=slot.end_time,
        is_break=slot.is_break,
        is_active=slot.is_active,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
        label=f"{_hhmm(slot.start_time)} – {_hhmm(slot.end_time)}",
        duration_minutes=max(_minutes(slot.end_time) - _minutes(slot.start_time), 0),
    )


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def validate_times(start: time, end: time) -> None:
    if _minutes(end) <= _minutes(start):
        raise _bad_request("A period must end after it starts.")


def ensure_no_overlap(
    db: Session,
    start: time,
    end: time,
    exclude_id: int | None = None,
) -> None:
    """Two periods may not cover the same minute.

    Overlap is checked against active periods only: a retired period is not
    part of the day, so it should not block the period replacing it.
    """
    query = db.query(TimeSlot).filter(TimeSlot.is_active.is_(True))
    if exclude_id is not None:
        query = query.filter(TimeSlot.id != exclude_id)

    new_start, new_end = _minutes(start), _minutes(end)
    for other in query.all():
        if new_start < _minutes(other.end_time) and _minutes(other.start_time) < new_end:
            raise _conflict(
                f"This overlaps {other.name} "
                f"({_hhmm(other.start_time)} – {_hhmm(other.end_time)})."
            )


def ensure_unique_period(db: Session, period_number: int, exclude_id: int | None = None) -> None:
    query = db.query(TimeSlot).filter(TimeSlot.period_number == period_number)
    if exclude_id is not None:
        query = query.filter(TimeSlot.id != exclude_id)
    if query.first():
        raise _conflict(DUPLICATE_PERIOD_DETAIL)


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_time_slots(db: Session, is_active: bool | None = None) -> list[TimeSlot]:
    query = db.query(TimeSlot)
    if is_active is not None:
        query = query.filter(TimeSlot.is_active == is_active)
    return query.order_by(TimeSlot.period_number.asc()).all()


def get_time_slot_or_404(db: Session, slot_id: int) -> TimeSlot:
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise _not_found("Time slot not found")
    return slot


def count_entries_for_slot(db: Session, slot_id: int) -> int:
    return db.query(TimetableEntry).filter(TimetableEntry.time_slot_id == slot_id).count()


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_time_slot(db: Session, payload: TimeSlotCreate) -> TimeSlot:
    validate_times(payload.start_time, payload.end_time)
    ensure_unique_period(db, payload.period_number)
    if payload.is_active:
        ensure_no_overlap(db, payload.start_time, payload.end_time)

    slot = TimeSlot(
        period_number=payload.period_number,
        name=payload.name.strip(),
        start_time=payload.start_time,
        end_time=payload.end_time,
        is_break=payload.is_break,
        is_active=payload.is_active,
    )

    try:
        db.add(slot)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(DUPLICATE_PERIOD_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the period. Please try again.")

    db.refresh(slot)
    return slot


def update_time_slot(db: Session, slot: TimeSlot, payload: TimeSlotUpdate) -> TimeSlot:
    validate_times(payload.start_time, payload.end_time)
    ensure_unique_period(db, payload.period_number, exclude_id=slot.id)
    if payload.is_active:
        ensure_no_overlap(db, payload.start_time, payload.end_time, exclude_id=slot.id)

    # Turning a period that already holds classes into a break would leave
    # those classes sitting inside the lunch hour.
    if payload.is_break and not slot.is_break:
        scheduled = count_entries_for_slot(db, slot.id)
        if scheduled:
            raise _conflict(
                f"{scheduled} class(es) are scheduled in this period. "
                "Move them before turning it into a break."
            )

    try:
        slot.period_number = payload.period_number
        slot.name = payload.name.strip()
        slot.start_time = payload.start_time
        slot.end_time = payload.end_time
        slot.is_break = payload.is_break
        slot.is_active = payload.is_active
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(DUPLICATE_PERIOD_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the period. Please try again.")

    db.refresh(slot)
    return slot


def delete_time_slot(db: Session, slot: TimeSlot) -> None:
    scheduled = count_entries_for_slot(db, slot.id)
    if scheduled:
        raise _conflict(
            f"{scheduled} class(es) are scheduled in this period. "
            "Remove them before deleting it, or deactivate the period instead."
        )

    try:
        db.delete(slot)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the period. Please try again.")


# --------------------------------------------------------------------------
# seeding
# --------------------------------------------------------------------------

DEFAULT_SLOTS = [
    (1, "Period 1", time(9, 0), time(9, 50), False),
    (2, "Period 2", time(9, 50), time(10, 40), False),
    (3, "Break", time(10, 40), time(10, 55), True),
    (4, "Period 3", time(10, 55), time(11, 45), False),
    (5, "Period 4", time(11, 45), time(12, 35), False),
    (6, "Lunch", time(12, 35), time(13, 20), True),
    (7, "Period 5", time(13, 20), time(14, 10), False),
    (8, "Period 6", time(14, 10), time(15, 0), False),
    (9, "Period 7", time(15, 0), time(15, 50), False),
]


def seed_default_slots(db: Session) -> None:
    """Give a fresh install a working day to schedule against.

    Idempotent, and it never touches a college that has already built its own
    schedule — the presence of any period at all is taken as "configured".
    """
    if db.query(TimeSlot).first():
        return

    for period_number, name, start, end, is_break in DEFAULT_SLOTS:
        db.add(
            TimeSlot(
                period_number=period_number,
                name=name,
                start_time=start,
                end_time=end,
                is_break=is_break,
                is_active=True,
            )
        )
    db.commit()
