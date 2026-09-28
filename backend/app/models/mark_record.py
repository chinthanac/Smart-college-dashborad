from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class MarkRecord(Base):
    """One student's standing in one assessment.

    ``marks_obtained`` is nullable, and NULL is not zero. NULL means nobody
    has entered a mark for this student yet, which leaves the assessment
    incomplete and excludes its subject from result computation entirely. A
    zero written in place of "not entered" would silently fail a student who
    was simply skipped, and it would do so in a number nobody can distinguish
    afterwards from a real zero.
    """

    __tablename__ = "mark_records"
    __table_args__ = (
        # A student appears at most once per component. Without this a double
        # submit would count them twice in the weighted total.
        UniqueConstraint(
            "assessment_id", "student_id", name="uq_mark_record_assessment_student"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    assessment_id = Column(Integer, ForeignKey("assessments.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)

    # Denormalized from the student at write time: the section they sat in on
    # the day this was entered. A student who transfers mid-semester keeps
    # their earlier marks attached to the section that actually taught them.
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)

    # NULL = not entered. See the class docstring.
    marks_obtained = Column(Float, nullable=True)

    # Both count as 0 toward the weighted total, and both are reported as
    # their own counts: "twelve absentees" and "twelve zeros" are different
    # facts about a class. is_absent requires marks_obtained to be NULL.
    is_absent = Column(Boolean, default=False, nullable=False, index=True)
    is_malpractice = Column(Boolean, default=False, nullable=False)

    remarks = Column(String(500), nullable=True)

    # Rewritten on every save, so it means "last corrected by", which is what
    # an audit actually needs.
    entered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    assessment = relationship("Assessment", back_populates="records")
    student = relationship("Student")
    entered_by = relationship("User")
