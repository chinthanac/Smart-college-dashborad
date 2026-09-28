from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AttendanceSession(Base):
    """One scheduled class on one real date — the register for that hour.

    The session points at a ``timetable_entry_id``, so "mark attendance for a
    class that was never scheduled" is structurally unreachable, exactly as the
    timetable entry makes an unscheduled teaching assignment unreachable.

    A session exists only once someone has actually marked the sheet. Opening
    the screen does not create one, because this row is the denominator of
    every percentage in the system: a session that appeared merely because a
    lecturer browsed next week would silently invent a class that happened.
    """

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        # One register per class per date. The service reports a duplicate with
        # the subject and the date; the constraint is the backstop for two tabs
        # — or the lecturer and an admin — saving the same sheet at once.
        UniqueConstraint(
            "timetable_entry_id", "class_date", name="uq_attendance_session_entry_date"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    timetable_entry_id = Column(
        Integer, ForeignKey("timetable_entries.id"), nullable=False, index=True
    )

    # Denormalized from the entry at write time, never accepted from the client
    # — the same pattern as TimetableEntry's own faculty/section/semester trio.
    # These are the columns every report filters and groups on, and they are
    # what keeps a register readable if the grid is later rearranged.
    teaching_assignment_id = Column(
        Integer, ForeignKey("teaching_assignments.id"), nullable=False, index=True
    )
    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False, index=True)

    class_date = Column(Date, nullable=False, index=True)

    # 0 = Monday … 6 = Sunday, matching datetime.date.weekday(). Copied from the
    # entry and proven equal to class_date.weekday() before every write.
    day_of_week = Column(Integer, nullable=False, index=True)

    # HELD / CANCELLED — a cancelled session keeps its row so the register
    # shows why the day is empty, but counts toward nobody's percentage.
    session_status = Column(String(20), nullable=False, default="HELD", index=True)
    cancel_reason = Column(String(500), nullable=True)
    notes = Column(String(500), nullable=True)

    # Who put their name to this sheet. Rewritten on every save, so it means
    # "last corrected by", which is what an audit actually needs.
    marked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    marked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    timetable_entry = relationship("TimetableEntry")
    teaching_assignment = relationship("TeachingAssignment")
    faculty = relationship("Faculty")
    subject = relationship("Subject")
    section = relationship("Section")
    semester = relationship("Semester")
    time_slot = relationship("TimeSlot")
    marked_by = relationship("User")

    # Deleting a session takes its records with it — a record with no date and
    # no subject means nothing. Note there is deliberately no back_populates on
    # TimetableEntry, TeachingAssignment or Section: those already cascade
    # delete-orphan downward, and a fourth link would extend that cascade into
    # attendance and destroy history when a section is removed. The register is
    # protected by the explicit count guards in attendance_service instead.
    records = relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )
