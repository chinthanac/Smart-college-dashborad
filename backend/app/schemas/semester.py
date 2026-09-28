from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SemesterBase(BaseModel):
    course_id: int = Field(..., gt=0)
    academic_year_id: int = Field(..., gt=0)
    semester_number: int = Field(..., ge=1, le=12)
    name: str = Field(..., min_length=2, max_length=100)
    start_date: date
    end_date: date
    is_active: bool = True


class SemesterCreate(SemesterBase):
    pass


class SemesterUpdate(SemesterBase):
    pass


class SemesterOut(SemesterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    course_name: str | None = None
    academic_year_name: str | None = None
