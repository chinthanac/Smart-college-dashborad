from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)
    capacity = Column(Integer, nullable=False)
    room_number = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    semester = relationship("Semester", back_populates="sections")
    # Semester.sections already cascades, so without this a deleted semester
    # would leave its sections' teaching assignments orphaned. Direct section
    # deletion is guarded in the router instead.
    teaching_assignments = relationship(
        "TeachingAssignment", back_populates="section", cascade="all, delete-orphan"
    )
