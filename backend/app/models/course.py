from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, index=True, nullable=False)
    degree = Column(String(100), nullable=False)
    duration_years = Column(Integer, nullable=False)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    department = relationship("Department", back_populates="courses")
    semesters = relationship("Semester", back_populates="course")
