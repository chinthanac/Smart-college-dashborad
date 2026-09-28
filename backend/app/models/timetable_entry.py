from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TimetableEntry(Base):
    """One scheduled class: a teaching assignment placed on a day and period.

    The entry points at a ``teaching_assignment_id`` rather than carrying its
    own faculty/subject/section trio, which makes "schedule a lecturer for a
    subject they do not teach" structurally unreachable — the same way the
    teaching assignment service makes an invalid subject/section pair
    unreachable.
    """

    __tablename__ = "timetable_entries"
    __table_args__ = (
        # A section cannot sit in two classes at once. The service reports this
        # with the name of the clashing subject; the constraint is the backstop
        # for two admins writing the same cell at the same moment.
        UniqueConstraint(
            "section_id", "day_of_week", "time_slot_id", name="uq_timetable_section_slot"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    teaching_assignment_id = Column(
        Integer, ForeignKey("teaching_assignments.id"), nullable=False, index=True
    )

    # Denormalized from the assignment at write time, never accepted from the
    # client — same pattern as TeachingAssignment.semester_id. These are the
    # indexes the three clash queries run on.
    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)

    # 0 = Monday … 6 = Sunday, matching datetime.date.weekday().
    day_of_week = Column(Integer, nullable=False, index=True)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False, index=True)

    # Defaults to the section's own room, overridden for labs and shared halls.
    room_number = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    teaching_assignment = relationship("TeachingAssignment", back_populates="timetable_entries")
    faculty = relationship("Faculty")
    section = relationship("Section")
    semester = relationship("Semester")
    time_slot = relationship("TimeSlot")
