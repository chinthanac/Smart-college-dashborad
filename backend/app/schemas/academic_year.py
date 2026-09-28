from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AcademicYearBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    start_date: date
    end_date: date
    is_current: bool = False


class AcademicYearCreate(AcademicYearBase):
    pass


class AcademicYearUpdate(AcademicYearBase):
    is_active: bool = True


class AcademicYearOut(AcademicYearBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
