from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeachingAssignmentBase(BaseModel):
    faculty_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class TeachingAssignmentCreate(TeachingAssignmentBase):
    pass


class TeachingAssignmentUpdate(TeachingAssignmentBase):
    pass


class TeachingAssignmentStatusUpdate(BaseModel):
    is_active: bool


class TeachingAssignmentBulkCreate(BaseModel):
    """Assign one faculty member to one subject across several sections."""

    faculty_id: int = Field(..., gt=0)
    subject_id: int = Field(..., gt=0)
    section_ids: list[int] = Field(..., min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class TeachingAssignmentSkipped(BaseModel):
    section_id: int
    section_name: str | None = None
    reason: str


class TeachingAssignmentOut(TeachingAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    semester_id: int
    created_at: datetime
    updated_at: datetime

    # faculty_code holds the Faculty.faculty_id *string* (e.g. "FAC001"), named
    # _code so it never collides with the integer foreign key above.
    faculty_name: str | None = None
    faculty_code: str | None = None
    faculty_designation: str | None = None
    faculty_department_id: int | None = None
    faculty_department_name: str | None = None
    faculty_department_code: str | None = None
    faculty_is_active: bool | None = None

    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    subject_credits: int | None = None
    subject_is_active: bool | None = None

    section_name: str | None = None
    section_code: str | None = None
    section_room_number: str | None = None
    section_capacity: int | None = None
    section_is_active: bool | None = None

    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    course_code: str | None = None
    # The subject's owning department, deliberately distinct from
    # faculty_department_* so the UI can show both when they differ.
    department_id: int | None = None
    department_name: str | None = None
    department_code: str | None = None
    academic_year_id: int | None = None
    academic_year_name: str | None = None

    is_cross_department: bool = False


class TeachingAssignmentBulkResult(BaseModel):
    created: list[TeachingAssignmentOut]
    skipped: list[TeachingAssignmentSkipped]
