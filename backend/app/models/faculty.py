from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Faculty(Base):
    __tablename__ = "faculty"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    faculty_id = Column(String(50), unique=True, index=True, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)
    designation = Column(String(50), nullable=False)
    qualification = Column(String(255), nullable=False)
    joining_date = Column(Date, nullable=False)
    employee_type = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    department = relationship("Department")
