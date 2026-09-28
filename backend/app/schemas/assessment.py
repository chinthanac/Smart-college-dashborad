"""Assessments — the gradable components of a subject.

This module also owns every institutional policy value the marks and results
modules read: the grade scale, the pass mark, the weightage budget. A college
whose scheme differs changes them here and nowhere else, which is the same
discipline ``ATTENDANCE_STATUSES`` and ``DEFAULT_ATTENDANCE_THRESHOLD`` keep
for attendance.

Two rules are worth stating where they will be read first:

  * an assessment's ``weightage_percent`` is its share of the subject's 100,
    and the sum across one teaching assignment may never exceed
    ``MAX_TOTAL_WEIGHTAGE`` — the sum is the denominator of the subject's
    final percentage, so an overflow makes every result that subject produces
    quietly wrong;
  * ``DRAFT`` reaches nobody. Not the student, not a report, not a dashboard
    figure. Publishing is the deliberate act that makes a mark real.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The gradable components a subject can be broken into. EXTERNAL is the
# end-of-semester university paper; the rest are internal to the college.
ASSESSMENT_TYPES = [
    "INTERNAL",
    "ASSIGNMENT",
    "LAB",
    "QUIZ",
    "MODEL",
    "EXTERNAL",
]

# DRAFT     - being prepared; invisible to students, excluded from every
#             aggregate, distribution and dashboard figure.
# PUBLISHED - marks are visible to students and counted.
# LOCKED    - frozen; faculty can no longer write. An admin may unlock, and
#             the unlock is stamped on the row.
ASSESSMENT_STATUSES = ["DRAFT", "PUBLISHED", "LOCKED"]

DEFAULT_ASSESSMENT_STATUS = "DRAFT"

# Statuses whose marks count toward a result. DRAFT is deliberately absent.
COUNTED_ASSESSMENT_STATUSES = ["PUBLISHED", "LOCKED"]

# Statuses a faculty member may no longer write marks into.
FROZEN_ASSESSMENT_STATUSES = ["LOCKED"]

# Total weightage one teaching assignment may allocate across its components.
MAX_TOTAL_WEIGHTAGE = 100.0

# Floating point sums of user-entered percentages land a hair either side of
# 100.0. Comparisons against the budget allow this much slack so that
# 30 + 30 + 40 is accepted.
WEIGHTAGE_EPSILON = 0.01

# Below this percentage of an assessment's max_marks, a student has failed it.
# Also the default for ``pass_marks`` when it is left unset.
PASS_PERCENT = 40.0

# The 10-point scale: (minimum percent, letter, grade point). Ordered high to
# low; the first band whose minimum is met wins.
GRADE_SCALE = [
    (90.0, "O", 10.0),
    (80.0, "A+", 9.0),
    (70.0, "A", 8.0),
    (60.0, "B+", 7.0),
    (55.0, "B", 6.0),
    (50.0, "C", 5.0),
    (40.0, "P", 4.0),
    (0.0, "F", 0.0),
]

# Attendance below this is *reported* alongside a result, never used to
# withhold it. Withholding a result is an administrative decision with an
# appeals process behind it; a service that enforces it silently produces a
# support ticket, not a policy.
RESULT_ATTENDANCE_FLAG_THRESHOLD = 75.0

AssessmentStatus = Literal["DRAFT", "PUBLISHED", "LOCKED"]

# The transitions the status endpoint accepts, as the UI names them.
AssessmentStatusAction = Literal["publish", "lock", "unlock"]


def grade_for(percent: float | None) -> tuple[str | None, float | None]:
    """The letter and grade point for a subject percentage.

    ``None`` in, ``(None, None)`` out: an ungraded subject has no letter, and
    an "F" standing in for "not computed yet" is exactly the fabrication the
    stats module forbids.
    """
    if percent is None:
        return None, None
    for minimum, letter, point in GRADE_SCALE:
        if percent >= minimum:
            return letter, point
    return None, None


def default_pass_marks(max_marks: float) -> float:
    return round(max_marks * PASS_PERCENT / 100.0, 2)


# --------------------------------------------------------------------------
# write payloads
# --------------------------------------------------------------------------

class AssessmentBase(BaseModel):
    # The anchor. Everything else about who/what/whom is copied from it.
    teaching_assignment_id: int = Field(..., gt=0)

    assessment_type: str = Field(..., max_length=30)
    name: str = Field(..., min_length=1, max_length=255)
    sequence_no: int = Field(default=1, ge=1, le=99)
    description: str | None = Field(default=None, max_length=1000)

    max_marks: float = Field(..., gt=0, le=1000)
    weightage_percent: float = Field(..., gt=0, le=MAX_TOTAL_WEIGHTAGE)
    # Left unset it becomes PASS_PERCENT of max_marks.
    pass_marks: float | None = Field(default=None, ge=0, le=1000)

    scheduled_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)


class AssessmentCreate(AssessmentBase):
    pass


class AssessmentUpdate(BaseModel):
    """Every field optional: the form edits one thing at a time.

    ``teaching_assignment_id`` is absent on purpose. Moving an assessment to
    another class would strand the marks already entered against a roster that
    never sat it; the operation is a delete and a create, and it should look
    like one.
    """

    assessment_type: str | None = Field(default=None, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sequence_no: int | None = Field(default=None, ge=1, le=99)
    description: str | None = Field(default=None, max_length=1000)

    max_marks: float | None = Field(default=None, gt=0, le=1000)
    weightage_percent: float | None = Field(default=None, gt=0, le=MAX_TOTAL_WEIGHTAGE)
    pass_marks: float | None = Field(default=None, ge=0, le=1000)

    scheduled_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    is_active: bool | None = None


class AssessmentStatusUpdate(BaseModel):
    action: AssessmentStatusAction
    # Why a locked sheet was reopened. Recorded on the row that unlocks it.
    reason: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------
# read payloads
# --------------------------------------------------------------------------

class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teaching_assignment_id: int
    faculty_id: int
    subject_id: int
    section_id: int
    semester_id: int

    assessment_type: str
    name: str
    sequence_no: int
    description: str | None = None

    max_marks: float
    weightage_percent: float
    pass_marks: float | None = None

    scheduled_date: date | None = None
    duration_minutes: int | None = None

    status: str
    created_by_user_id: int
    published_at: datetime | None = None
    locked_by_user_id: int | None = None
    locked_at: datetime | None = None

    is_active: bool
    created_at: datetime
    updated_at: datetime

    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    subject_credits: int | None = None

    faculty_name: str | None = None
    faculty_code: str | None = None
    faculty_department_id: int | None = None

    section_name: str | None = None
    section_code: str | None = None

    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    course_code: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    academic_year_id: int | None = None
    academic_year_name: str | None = None

    created_by_name: str | None = None
    locked_by_name: str | None = None

    # Entry progress, so a list row can say "38 of 52 entered" without a
    # second request per assessment.
    total_students: int = 0
    entered_count: int = 0
    pending_count: int = 0
    absent_count: int = 0
    is_complete: bool = False

    # Only over the marks actually entered. 0.0 with entered_count == 0 means
    # "nothing yet", which is what is_complete is for.
    average_marks: float = 0.0
    average_percent: float = 0.0
    highest_marks: float | None = None
    lowest_marks: float | None = None
    pass_count: int = 0
    fail_count: int = 0

    editable_by_faculty: bool = True
    counts_toward_result: bool = False


class WeightageConsumer(BaseModel):
    """One component already claiming part of a class's 100%."""

    assessment_id: int
    name: str
    assessment_type: str
    weightage_percent: float
    status: str


class WeightageBudget(BaseModel):
    """What is left of a class's 100%, and what has taken the rest.

    The consumers are carried so a rejection can name them. "Internal 1 (30%)
    and Assignment 1 (20%) already allocate 50%; 50% remains" is actionable;
    "invalid weightage" makes the user guess.
    """

    teaching_assignment_id: int
    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None

    max_total: float = MAX_TOTAL_WEIGHTAGE
    allocated: float = 0.0
    remaining: float = MAX_TOTAL_WEIGHTAGE
    is_fully_allocated: bool = False

    consumers: list[WeightageConsumer] = []


class AssessmentOptions(BaseModel):
    types: list[str]
    statuses: list[str]
    counted_statuses: list[str]
    default_status: str
    max_total_weightage: float
    pass_percent: float
    grade_scale: list[dict]
    attendance_flag_threshold: float
