from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# PRESENT / ABSENT / LATE / EXCUSED. LATE still counts as having attended;
# EXCUSED (medical leave, college duty) leaves the denominator entirely rather
# than counting against the student.
ATTENDANCE_STATUSES = [
    "PRESENT",
    "ABSENT",
    "LATE",
    "EXCUSED",
]

PRESENT_STATUSES = ["PRESENT", "LATE"]
EXCUSED_STATUSES = ["EXCUSED"]

# HELD / CANCELLED. A cancelled session keeps its row so the register shows why
# the day is empty, but it contributes to nobody's percentage.
SESSION_STATUSES = ["HELD", "CANCELLED"]

DEFAULT_RECORD_STATUS = "PRESENT"
DEFAULT_SESSION_STATUS = "HELD"

# How far back a faculty member may mark. Admins are not bounded — correcting
# an old register is exactly their job.
ATTENDANCE_BACKDATE_DAYS = 30

# Below this a student is a defaulter in the section report.
DEFAULT_ATTENDANCE_THRESHOLD = 75.0

# NO_DATA when nothing countable has happened yet; AT_RISK within five points
# above the threshold; SHORT below it.
AttendanceStanding = Literal["NO_DATA", "AT_RISK", "SHORT", "GOOD"]


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

class AttendanceRecordBase(BaseModel):
    student_id: int = Field(..., gt=0)
    status: str = Field(default=DEFAULT_RECORD_STATUS, max_length=20)
    remarks: str | None = Field(default=None, max_length=500)


class AttendanceRecordCreate(AttendanceRecordBase):
    pass


class AttendanceRecordUpdate(AttendanceRecordBase):
    pass


class AttendanceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # None on a draft row — the student is on the roster but nothing is saved
    # for them yet.
    id: int | None = None
    attendance_session_id: int | None = None
    student_id: int
    section_id: int | None = None
    status: str
    remarks: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    student_code: str | None = None
    student_name: str | None = None
    student_email: str | None = None
    student_status: str | None = None
    student_section_id: int | None = None
    student_section_name: str | None = None

    is_present: bool = False

    # True when the record was marked against a section the student has since
    # left — surfaces a mid-semester transfer instead of hiding it.
    moved_section: bool = False


# --------------------------------------------------------------------------
# sessions
# --------------------------------------------------------------------------

class AttendanceSessionBase(BaseModel):
    timetable_entry_id: int = Field(..., gt=0)
    class_date: date
    session_status: str = Field(default=DEFAULT_SESSION_STATUS, max_length=20)
    cancel_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=500)


class AttendanceSessionCreate(AttendanceSessionBase):
    pass


class AttendanceSessionUpdate(AttendanceSessionBase):
    pass


class AttendanceSessionStatusUpdate(BaseModel):
    session_status: str = Field(..., max_length=20)
    cancel_reason: str | None = Field(default=None, max_length=500)


class AttendanceSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timetable_entry_id: int
    teaching_assignment_id: int
    faculty_id: int
    subject_id: int
    section_id: int
    semester_id: int
    time_slot_id: int
    class_date: date
    day_of_week: int
    session_status: str
    cancel_reason: str | None = None
    notes: str | None = None
    marked_by_user_id: int
    marked_at: datetime
    is_active: bool
    created_at: datetime
    updated_at: datetime

    day_name: str | None = None

    period_number: int | None = None
    slot_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    slot_label: str | None = None

    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None

    faculty_name: str | None = None
    faculty_code: str | None = None
    faculty_department_id: int | None = None

    section_name: str | None = None
    section_code: str | None = None
    section_room_number: str | None = None
    room_number: str | None = None

    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    course_code: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    academic_year_id: int | None = None
    academic_year_name: str | None = None

    marked_by_name: str | None = None
    marked_by_role: str | None = None

    total_students: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    # Records that count toward a percentage: everything except EXCUSED.
    countable_count: int = 0
    attendance_percentage: float = 0.0

    is_cancelled: bool = False


# --------------------------------------------------------------------------
# the marking sheet
# --------------------------------------------------------------------------

class AttendanceSheetSave(BaseModel):
    timetable_entry_id: int = Field(..., gt=0)
    class_date: date
    session_status: str = Field(default=DEFAULT_SESSION_STATUS, max_length=20)
    cancel_reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=500)
    records: list[AttendanceRecordCreate] = []


class AttendanceSheet(BaseModel):
    """Everything the marking screen needs in one payload."""

    timetable_entry_id: int
    class_date: date
    day_name: str | None = None

    # None until the sheet has been saved once. Opening a sheet never creates
    # a session — a session is the denominator of every percentage.
    session: AttendanceSessionOut | None = None
    records: list[AttendanceRecordOut] = []

    sheet_state: Literal["DRAFT", "MARKED", "CANCELLED"] = "DRAFT"
    editable: bool = True
    locked_reason: str | None = None

    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    section_code: str | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    slot_name: str | None = None
    slot_label: str | None = None
    room_number: str | None = None

    total_students: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    countable_count: int = 0
    attendance_percentage: float = 0.0


class MarkableClassOut(BaseModel):
    """One row in a faculty member's "what do I mark today" list."""

    timetable_entry_id: int
    teaching_assignment_id: int
    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    section_code: str | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None

    time_slot_id: int
    period_number: int | None = None
    slot_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    slot_label: str | None = None
    room_number: str | None = None

    class_date: date
    day_of_week: int
    day_name: str | None = None
    entry_is_active: bool = True

    session_id: int | None = None
    session_status: str | None = None
    marked: bool = False
    marked_at: datetime | None = None
    marked_by_name: str | None = None

    total_students: int = 0
    present_count: int = 0
    attendance_percentage: float = 0.0

    # PAUSED wins over UNMARKED: the class is shown so it does not look
    # missing, but its sheet refuses to open.
    status: Literal["UNMARKED", "MARKED", "CANCELLED", "PAUSED"] = "UNMARKED"


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

class SubjectAttendanceSummary(BaseModel):
    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    teaching_assignment_id: int | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None

    held_sessions: int = 0
    countable_sessions: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    attendance_percentage: float = 0.0
    status: AttendanceStanding = "NO_DATA"


class StudentAttendanceSummary(BaseModel):
    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None

    from_date: date | None = None
    to_date: date | None = None
    threshold: float = DEFAULT_ATTENDANCE_THRESHOLD

    overall_held: int = 0
    overall_countable: int = 0
    overall_present: int = 0
    overall_percentage: float = 0.0
    status: AttendanceStanding = "NO_DATA"

    subjects: list[SubjectAttendanceSummary] = []


class SectionAttendanceRow(BaseModel):
    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    student_status: str | None = None

    held_sessions: int = 0
    countable_sessions: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    attendance_percentage: float = 0.0
    status: AttendanceStanding = "NO_DATA"


class SectionAttendanceReport(BaseModel):
    section_id: int
    section_name: str | None = None
    section_code: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None

    subject_id: int | None = None
    subject_name: str | None = None

    from_date: date | None = None
    to_date: date | None = None
    threshold: float = DEFAULT_ATTENDANCE_THRESHOLD

    total_sessions: int = 0
    held_sessions: int = 0
    cancelled_sessions: int = 0
    total_students: int = 0
    defaulter_count: int = 0
    section_percentage: float = 0.0

    students: list[SectionAttendanceRow] = []


class AttendanceOptions(BaseModel):
    statuses: list[str]
    session_statuses: list[str]
    present_statuses: list[str]
    excused_statuses: list[str]
    default_status: str
    backdate_days: int
    default_threshold: float
