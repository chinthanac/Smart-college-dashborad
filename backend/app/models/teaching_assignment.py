from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TeachingAssignment(Base):
    __tablename__ = "teaching_assignments"

    # Exactly one faculty member teaches a given subject to a given section.
    # Re-assigning edits this row rather than adding a second one.
    __table_args__ = (
        UniqueConstraint("subject_id", "section_id", name="uq_teaching_assignment_subject_section"),
    )

    id = Column(Integer, primary_key=True, index=True)

    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)

    # Denormalized from subject.semester_id, which the service proves equal to
    # section.semester_id before every write. It is the anchor of the integrity
    # rule and keeps the faculty "/me" query to a single join.
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)

    notes = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    faculty = relationship("Faculty")
    subject = relationship("Subject")
    # Section.teaching_assignments already cascades, so without this a deleted
    # section would leave its scheduled classes behind as orphans.
    timetable_entries = relationship(
        "TimetableEntry", back_populates="teaching_assignment", cascade="all, delete-orphan"
    )
    section = relationship("Section", back_populates="teaching_assignments")
    semester = relationship("Semester")
