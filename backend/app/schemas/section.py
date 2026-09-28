from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SectionBase(BaseModel):
    semester_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    capacity: int = Field(..., gt=0)
    room_number: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True


class SectionCreate(SectionBase):
    pass


class SectionUpdate(SectionBase):
    pass


class SectionOut(SectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    semester_name: str | None = None
    course_name: str | None = None
    academic_year_name: str | None = None
