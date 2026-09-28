from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    student_id = Column(String(50), unique=True, index=True, nullable=False)

    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(30), nullable=True)
    phone = Column(String(20), nullable=False)
    address = Column(String(500), nullable=True)

    # The academic placement. Every id is verified against the one above it
    # before a student is written, so the chain can never be inconsistent.
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False, index=True)

    admission_date = Column(Date, nullable=True)
    # ACTIVE / INACTIVE / GRADUATED / SUSPENDED — students are never deleted
    # on graduation or exit, so their academic history stays intact.
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    department = relationship("Department")
    course = relationship("Course")
    academic_year = relationship("AcademicYear")
    semester = relationship("Semester")
    section = relationship("Section")
