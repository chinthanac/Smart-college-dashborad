from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseBase(BaseModel):
    department_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=50)
    degree: str = Field(..., min_length=2, max_length=100)
    duration_years: int = Field(..., ge=1, le=6)
    description: str | None = Field(default=None, max_length=1000)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(CourseBase):
    is_active: bool = True


class CourseOut(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    department_name: str | None = None
    department_code: str | None = None
