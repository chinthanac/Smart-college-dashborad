from sqlalchemy import Boolean, Column, DateTime, Integer, String, Time, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class TimeSlot(Base):
    """One period in the college's daily bell schedule.

    Times live here rather than on every timetable entry so that a clash is a
    plain integer comparison on ``time_slot_id`` instead of interval overlap
    arithmetic, and so moving the lunch break rewrites one row instead of
    every class in the college.
    """

    __tablename__ = "time_slots"
    __table_args__ = (
        UniqueConstraint("period_number", name="uq_time_slot_period"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # The ordering key for the grid. Breaks occupy a period number too, so the
    # day reads top to bottom without gaps.
    period_number = Column(Integer, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # A break renders as a full-width band across the grid and refuses to hold
    # a class.
    is_break = Column(Boolean, default=False, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
