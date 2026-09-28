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


class AttendanceRecord(Base):
    """One student's standing in one session."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        # A student appears at most once on a sheet. Without this a double
        # submit would count them twice in the denominator and quietly halve
        # their percentage.
        UniqueConstraint(
            "attendance_session_id", "student_id", name="uq_attendance_record_session_student"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    attendance_session_id = Column(
        Integer, ForeignKey("attendance_sessions.id"), nullable=False, index=True
    )
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)

    # Denormalized from the student at write time: the section they sat in on
    # the day this was marked. A student who transfers mid-semester keeps their
    # earlier records attached to the section that actually taught them.
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)

    # PRESENT / ABSENT / LATE / EXCUSED. LATE still counts as having attended;
    # EXCUSED leaves the denominator rather than counting against the student.
    status = Column(String(20), nullable=False, default="PRESENT", index=True)
    remarks = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("Student")
