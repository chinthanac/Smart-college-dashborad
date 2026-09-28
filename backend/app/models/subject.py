from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)

    # A subject belongs to a course and to one semester within it. The
    # semester is verified to belong to the course before any write.
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)

    subject_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)

    credits = Column(Integer, nullable=False)
    # THEORY / LAB / PROJECT / SEMINAR / ELECTIVE — attendance and marks
    # will later be calculated differently per type.
    subject_type = Column(String(30), nullable=False, index=True)

    lecture_hours = Column(Integer, nullable=False, default=0)
    tutorial_hours = Column(Integer, nullable=False, default=0)
    practical_hours = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Deliberately NO faculty_id here: the same subject is taught by
    # different faculty for different sections, so teaching assignments
    # live in their own table (the next module).
    course = relationship("Course")
    semester = relationship("Semester")
