"""Dashboard statistics.

--------------------------------------------------------------------------
What must NEVER be added to this module
--------------------------------------------------------------------------

  * a grade or GPA figure that is not derived from a PUBLISHED mark. The
    assessments module now exists, so marks are no longer fabrication — but
    a DRAFT component reaches nobody, and a student whose sheet is
    incomplete has no grade rather than a zero. ``results_service`` is the
    only place allowed to decide that, and this module reports what it
    returns rather than recomputing it;
  * events, notices or a calendar — there is no model behind them;
  * trend deltas, "vs last month", growth rates — nothing stores a prior
    period, so every delta would be the hardcoded 0.0% this endpoint was
    written to replace;
  * forecasts or predictions;
  * a zero standing in for "we do not know". Where a value is unknowable the
    payload says ``has_data: False`` and the UI renders an empty state.

The dashboard this feeds is the first screen an admin sees. A smaller one
that is entirely true beats a fuller one that is mostly invented.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

# How many calendar months the attendance series carries. Anchored on the
# newest HELD session rather than on today: a window pinned to "now" would
# draw twelve empty buckets for a college whose term ended last year, which
# reads as a broken chart rather than an old one.
MONTHLY_SERIES_MONTHS = 12

# Fullest sections shown in the capacity panel.
SECTION_FILL_LIMIT = 8

# Registers listed in the recent-activity panel.
RECENT_REGISTER_LIMIT = 6

# Departments drawn as their own slice before the rest fold into "Other".
DEPARTMENT_SLICE_LIMIT = 6

# Subjects listed in the assessment panel, worst pass rate first — the ones
# an admin would actually act on.
SUBJECT_RESULT_LIMIT = 8


class CountStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    departments: int = 0
    courses: int = 0
    academic_years: int = 0
    semesters: int = 0
    sections: int = 0
    faculty: int = 0
    active_faculty: int = 0
    students: int = 0
    active_students: int = 0
    subjects: int = 0
    teaching_assignments: int = 0
    timetable_entries: int = 0


class DepartmentStudentCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    department_id: int
    department_code: str | None = None
    department_name: str | None = None
    student_count: int = 0


class AttendanceStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_date: date | None = None
    to_date: date | None = None

    held_sessions: int = 0
    cancelled_sessions: int = 0

    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    countable_count: int = 0

    attendance_percentage: float = 0.0

    # False means "nothing has been marked", which is a different statement
    # from "attendance is 0%".
    has_data: bool = False


class MonthlyAttendancePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: str            # "2025-02"
    label: str            # "Feb 2025"
    held_sessions: int = 0
    present_count: int = 0
    countable_count: int = 0
    attendance_percentage: float = 0.0
    has_data: bool = False


class AttendanceSeries(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    months: list[MonthlyAttendancePoint] = []

    # The newest month carrying data — what the window is anchored on.
    anchor_month: str | None = None
    anchor_label: str | None = None

    # False when the newest data is not from the current month, which lets
    # the UI say "latest data is from Feb 2025" instead of showing a chart
    # that looks empty.
    is_current_period: bool = False
    has_data: bool = False


class TodayStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    class_date: date
    day_of_week: int
    day_name: str | None = None

    scheduled_classes: int = 0
    marked_sessions: int = 0
    cancelled_sessions: int = 0
    unmarked_classes: int = 0


class SectionFillRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    section_id: int
    section_name: str | None = None
    section_code: str | None = None
    semester_name: str | None = None
    capacity: int = 0
    enrolled: int = 0
    fill_percentage: float = 0.0
    over_capacity: bool = False


class RecentRegisterRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    class_date: date
    day_name: str | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    section_name: str | None = None
    section_code: str | None = None
    faculty_name: str | None = None
    session_status: str
    present_count: int = 0
    countable_count: int = 0
    attendance_percentage: float = 0.0


class SubjectPassRow(BaseModel):
    """One subject's standing across the college, worst first."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    faculty_name: str | None = None

    graded_students: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0
    average_percent: float | None = None


class GradeBandCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grade_letter: str
    grade_point: float
    student_count: int = 0
    percentage: float = 0.0


class AssessmentStats(BaseModel):
    """What the assessments module knows, as the dashboard may state it.

    Every count here is over PUBLISHED or LOCKED components only. The draft
    count is carried separately and deliberately excluded from everything
    else, because a draft reaches nobody.
    """

    model_config = ConfigDict(from_attributes=True)

    total_assessments: int = 0
    draft_assessments: int = 0
    published_assessments: int = 0
    locked_assessments: int = 0

    # Sheets that are still missing at least one mark. This is the number an
    # admin chases at the end of a term.
    incomplete_sheets: int = 0
    marks_recorded: int = 0

    graded_results: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0

    distribution: list[GradeBandCount] = []
    weakest_subjects: list[SubjectPassRow] = []

    # False means "nothing has been published yet", which is a different
    # statement from "the pass rate is 0%".
    has_data: bool = False


class DashboardStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime

    counts: CountStats
    students_by_department: list[DepartmentStudentCount] = []
    attendance: AttendanceStats
    attendance_series: AttendanceSeries
    today: TodayStats
    section_fill: list[SectionFillRow] = []
    recent_registers: list[RecentRegisterRow] = []
    assessments: AssessmentStats = AssessmentStats()

    # Teaching assignments with nothing on the timetable — the one number
    # that turns this page from decorative into actionable.
    unscheduled_assignments: int = 0
