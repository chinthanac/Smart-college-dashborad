from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class TimeSlotBase(BaseModel):
    period_number: int = Field(..., gt=0, le=20)
    name: str = Field(..., min_length=1, max_length=50)
    start_time: time
    end_time: time
    is_break: bool = False
    is_active: bool = True


class TimeSlotCreate(TimeSlotBase):
    pass


class TimeSlotUpdate(TimeSlotBase):
    pass


class TimeSlotOut(TimeSlotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    # "09:00 – 09:50", built once here so every screen labels a period the same way.
    label: str | None = None
    duration_minutes: int = 0
