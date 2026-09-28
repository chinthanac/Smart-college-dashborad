from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 0 = Monday … 6 = Sunday, matching datetime.date.weekday().
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# The default working week. Saturday and Sunday remain schedulable — plenty of
# colleges run Saturday classes — this only decides what the grid shows first.
DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4, 5]


class TimetableEntryBase(BaseModel):
    teaching_assignment_id: int = Field(..., gt=0)
    day_of_week: int = Field(..., ge=0, le=6)
    time_slot_id: int = Field(..., gt=0)
    # Left empty, the section's own room is used.
    room_number: str | None = Field(default=None, max_length=100)
    is_active: bool = True


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(TimetableEntryBase):
    pass


class TimetableEntryStatusUpdate(BaseModel):
    is_active: bool


class TimetableEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teaching_assignment_id: int
    faculty_id: int
    section_id: int
    semester_id: int
    day_of_week: int
    time_slot_id: int
    room_number: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    day_name: str | None = None

    period_number: int | None = None
    slot_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    slot_label: str | None = None

    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    subject_credits: int | None = None

    faculty_name: str | None = None
    faculty_code: str | None = None
    faculty_department_id: int | None = None

    section_name: str | None = None
    section_code: str | None = None
    section_room_number: str | None = None

    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    course_code: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    academic_year_id: int | None = None
    academic_year_name: str | None = None

    # True when the class sits somewhere other than its section's home room —
    # the normal case for labs, and worth flagging in the grid.
    is_relocated: bool = False


class TimetableCopyDay(BaseModel):
    """Duplicate one section's day onto another day of the same week."""

    section_id: int = Field(..., gt=0)
    from_day: int = Field(..., ge=0, le=6)
    to_day: int = Field(..., ge=0, le=6)


class TimetableCopySkipped(BaseModel):
    time_slot_id: int
    slot_label: str | None = None
    reason: str


class TimetableCopyResult(BaseModel):
    created: list[TimetableEntryOut]
    skipped: list[TimetableCopySkipped]


class SubjectCoverage(BaseModel):
    """Required weekly periods versus what is actually on the grid."""

    teaching_assignment_id: int
    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    faculty_id: int
    faculty_name: str | None = None

    lecture_hours: int = 0
    tutorial_hours: int = 0
    practical_hours: int = 0
    required_periods: int = 0
    scheduled_periods: int = 0
    remaining_periods: int = 0

    status: Literal["UNSCHEDULED", "UNDER_SCHEDULED", "COMPLETE", "OVER_SCHEDULED"]


class SectionCoverage(BaseModel):
    section_id: int
    section_name: str | None = None
    section_code: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None
    total_required: int = 0
    total_scheduled: int = 0
    subjects: list[SubjectCoverage]
