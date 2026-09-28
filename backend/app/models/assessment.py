from sqlalchemy import (
    Boolean,
    Column,
    Date,
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


class Assessment(Base):
    """One gradable component of one subject for one section.

    The assessment points at a ``teaching_assignment_id``, so "create an exam
    for a subject nobody teaches to that section" is structurally unreachable,
    exactly as the timetable entry makes an unscheduled teaching assignment
    unreachable and the attendance session makes an unscheduled class
    unreachable.

    An assessment is born DRAFT. Nothing in DRAFT reaches a student or any
    aggregate: publishing is the deliberate act that makes a mark real, and
    locking is the act that freezes it. The weightage it claims is checked
    against every sibling on the same assignment, because the sum of those
    weightages is the denominator of the subject's final percentage — let it
    pass 100 and every result the subject produces is quietly wrong.
    """

    __tablename__ = "assessments"
    __table_args__ = (
        # One "Internal 1" per class. The service reports a duplicate with the
        # subject and the component name; the constraint is the backstop for
        # two tabs — or the lecturer and an admin — creating it at once.
        UniqueConstraint(
            "teaching_assignment_id",
            "assessment_type",
            "sequence_no",
            name="uq_assessment_assignment_type_seq",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    teaching_assignment_id = Column(
        Integer, ForeignKey("teaching_assignments.id"), nullable=False, index=True
    )

    # Denormalized from the assignment at write time, never accepted from the
    # client — the same pattern as AttendanceSession's faculty/subject/section
    # trio. These are the columns every report filters and groups on.
    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)

    # INTERNAL / ASSIGNMENT / LAB / QUIZ / MODEL / EXTERNAL
    assessment_type = Column(String(30), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    # Distinguishes "Internal 1" from "Internal 2" on the same class, and
    # orders the components on a mark sheet.
    sequence_no = Column(Integer, nullable=False, default=1)
    description = Column(String(1000), nullable=True)

    # The denominator of every percentage this component produces, so the
    # service refuses anything at or below zero.
    max_marks = Column(Float, nullable=False)
    # This component's share of the subject's 100. The sum across one
    # teaching assignment may never exceed MAX_TOTAL_WEIGHTAGE.
    weightage_percent = Column(Float, nullable=False)
    # Defaults to PASS_PERCENT of max_marks when left unset.
    pass_marks = Column(Float, nullable=True)

    scheduled_date = Column(Date, nullable=True, index=True)
    duration_minutes = Column(Integer, nullable=True)

    # DRAFT / PUBLISHED / LOCKED
    status = Column(String(20), nullable=False, default="DRAFT", index=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    # Who froze the sheet, and who unfroze it. Correcting a locked mark sheet
    # is an administrative act and should leave a trace.
    locked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    teaching_assignment = relationship("TeachingAssignment")
    faculty = relationship("Faculty")
    subject = relationship("Subject")
    section = relationship("Section")
    semester = relationship("Semester")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    locked_by = relationship("User", foreign_keys=[locked_by_user_id])

    # Deleting an assessment takes its marks with it — a mark with no
    # component and no maximum means nothing. Note there is deliberately no
    # back_populates on TeachingAssignment: Section already cascades
    # delete-orphan into teaching_assignments, and a link here would extend
    # that cascade into exam history, so removing a section would destroy
    # every mark it ever received. Assessments are protected by the explicit
    # count guards in assessment_service instead, exactly as the attendance
    # register is.
    records = relationship(
        "MarkRecord", back_populates="assessment", cascade="all, delete-orphan"
    )
