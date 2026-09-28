from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

DESIGNATIONS = [
    "Professor",
    "Associate Professor",
    "Assistant Professor",
    "Lecturer",
    "Visiting Faculty",
]

EMPLOYEE_TYPES = [
    "Full Time",
    "Part Time",
    "Contract",
    "Visiting",
]


class FacultyBase(BaseModel):
    faculty_id: str = Field(..., min_length=2, max_length=50)
    department_id: int = Field(..., gt=0)
    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    phone: str = Field(..., min_length=6, max_length=20)
    designation: str = Field(..., min_length=2, max_length=50)
    qualification: str = Field(..., min_length=1, max_length=255)
    joining_date: date
    employee_type: str = Field(..., min_length=2, max_length=50)
    is_active: bool = True


class FacultyCreate(FacultyBase):
    email: str = Field(..., min_length=5, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class FacultyUpdate(FacultyBase):
    email: str = Field(..., min_length=5, max_length=255)


class FacultyStatusUpdate(BaseModel):
    is_active: bool


class FacultyProfileUpdate(BaseModel):
    """The subset of fields a faculty member may change on their own profile."""

    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    phone: str = Field(..., min_length=6, max_length=20)
    qualification: str = Field(..., min_length=1, max_length=255)


class FacultyPasswordReset(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class FacultyOut(FacultyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str
    full_name: str
    created_at: datetime
    updated_at: datetime

    department_name: str | None = None
    department_code: str | None = None


class FacultyCreated(FacultyOut):
    """Returned once on creation/reset so the Admin can hand over credentials."""

    generated_password: str | None = None


class FacultyOptions(BaseModel):
    designations: list[str]
    employee_types: list[str]
