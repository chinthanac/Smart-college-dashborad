from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

SUBJECT_TYPES = [
    "THEORY",
    "LAB",
    "PROJECT",
    "SEMINAR",
    "ELECTIVE",
]


class SubjectBase(BaseModel):
    course_id: int = Field(..., gt=0)
    semester_id: int = Field(..., gt=0)
    subject_code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    credits: int = Field(..., gt=0)
    subject_type: str = Field(..., max_length=30)
    lecture_hours: int = Field(default=0, ge=0)
    tutorial_hours: int = Field(default=0, ge=0)
    practical_hours: int = Field(default=0, ge=0)
    is_active: bool = True


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(SubjectBase):
    pass


class SubjectStatusUpdate(BaseModel):
    is_active: bool


class SubjectOut(SubjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    total_hours: int = 0

    course_name: str | None = None
    course_code: str | None = None
    semester_name: str | None = None
    semester_number: int | None = None
    academic_year_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    department_code: str | None = None


class SubjectOptions(BaseModel):
    subject_types: list[str]
