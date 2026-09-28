from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False, index=True)
    semester_number = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    course = relationship("Course", back_populates="semesters")
    academic_year = relationship("AcademicYear", back_populates="semesters")
    sections = relationship("Section", back_populates="semester", cascade="all, delete-orphan")
