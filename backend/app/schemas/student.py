from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

GENDERS = [
    "Male",
    "Female",
    "Other",
    "Prefer not to say",
]

STATUSES = [
    "ACTIVE",
    "INACTIVE",
    "GRADUATED",
    "SUSPENDED",
]

# Only ACTIVE students may sign in; the rest keep their records but lose access.
LOGIN_ALLOWED_STATUSES = {"ACTIVE"}


class StudentBase(BaseModel):
    student_id: str = Field(..., min_length=2, max_length=50)

    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)
    phone: str = Field(..., min_length=6, max_length=20)
    address: str | None = Field(default=None, max_length=500)

    department_id: int = Field(..., gt=0)
    course_id: int = Field(..., gt=0)
    academic_year_id: int = Field(..., gt=0)
    semester_id: int = Field(..., gt=0)
    section_id: int = Field(..., gt=0)

    admission_date: date | None = None
    status: str = Field(default="ACTIVE", max_length=20)


class StudentCreate(StudentBase):
    email: str = Field(..., min_length=5, max_length=255)
    # Approach A: the Admin sets a temporary password. Left empty, the
    # backend generates one and hands it back exactly once.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class StudentUpdate(StudentBase):
    email: str = Field(..., min_length=5, max_length=255)


class StudentStatusUpdate(BaseModel):
    status: str = Field(..., max_length=20)


class StudentProfileUpdate(BaseModel):
    """The subset a student may change on their own profile."""

    phone: str = Field(..., min_length=6, max_length=20)
    address: str | None = Field(default=None, max_length=500)


class StudentPasswordReset(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=128)


class StudentOut(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email: str
    full_name: str
    created_at: datetime
    updated_at: datetime

    department_name: str | None = None
    department_code: str | None = None
    course_name: str | None = None
    course_code: str | None = None
    academic_year_name: str | None = None
    semester_name: str | None = None
    semester_number: int | None = None
    section_name: str | None = None
    section_code: str | None = None


class StudentCreated(StudentOut):
    """Returned once on creation/reset so the Admin can hand over credentials."""

    generated_password: str | None = None


class StudentOptions(BaseModel):
    genders: list[str]
    statuses: list[str]


class StudentIdSuggestion(BaseModel):
    suggested_student_id: str
