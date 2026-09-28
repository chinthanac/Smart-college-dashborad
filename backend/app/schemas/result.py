"""Results — derived, never stored.

A stored grade is a second source of truth. Marks are corrected constantly,
and the moment one is, a stored row is wrong until something recomputes it —
and nothing guarantees that something runs. Derivation is cheap here (a
section is a few hundred rows) and it is always right.

What this module will not do, for the same reason ``schemas/stats.py`` keeps
its own prohibition list:

  * report a partial SGPA. If any credit-bearing subject lacks a final grade
    the payload says ``has_data: False`` and carries the reason. A partial
    SGPA is worse than none: it will be screenshotted and believed;
  * let a zero stand in for "not computed". An ungraded subject has no
    letter, not an F;
  * count a DRAFT assessment anywhere;
  * withhold a result over attendance. Shortage is reported as a flag — see
    ``RESULT_ATTENDANCE_FLAG_THRESHOLD``.

The weighted formula, for one student and one subject::

    subject_percent = sum over counted assessments of
                          (effective_marks / max_marks) * weightage_percent
                      -----------------------------------------------------
                                  sum of weightage_percent

    effective_marks = 0.0 if (is_absent or is_malpractice) else marks_obtained

Dividing by the *allocated* weightage rather than by 100 means a subject that
has run two of its three components reports an honest percentage of what has
happened so far, instead of appearing to have failed the missing third.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.assessment import RESULT_ATTENDANCE_FLAG_THRESHOLD


class AssessmentBreakdown(BaseModel):
    """One component's contribution to a student's subject percentage."""

    model_config = ConfigDict(from_attributes=True)

    assessment_id: int
    name: str
    assessment_type: str
    sequence_no: int
    status: str

    max_marks: float
    weightage_percent: float
    pass_marks: float | None = None

    marks_obtained: float | None = None
    is_absent: bool = False
    is_malpractice: bool = False

    percent: float | None = None
    # weightage_percent * (effective_marks / max_marks)
    weighted_contribution: float | None = None
    is_pass: bool | None = None
    # True when nothing is entered for this student yet — the flag that
    # excludes the whole subject from the result.
    is_pending: bool = True


class SubjectResult(BaseModel):
    """One student in one subject."""

    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    credits: int | None = None

    teaching_assignment_id: int | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    section_id: int | None = None
    section_name: str | None = None

    # Weightage of the counted components, which is the denominator above.
    allocated_weightage: float = 0.0
    assessments_total: int = 0
    assessments_counted: int = 0
    assessments_pending: int = 0

    # None, not 0.0, whenever the subject is incomplete.
    percent: float | None = None
    grade_letter: str | None = None
    grade_point: float | None = None
    is_pass: bool | None = None

    # False when any counted component has no mark for this student.
    has_data: bool = False
    reason: str | None = None

    breakdown: list[AssessmentBreakdown] = []


class StudentResult(BaseModel):
    """One student's standing across a semester."""

    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    student_status: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None

    subjects: list[SubjectResult] = []

    total_credits: int = 0
    # Credits behind a completed subject. sgpa is computed over these only.
    earned_credits: int = 0
    subjects_complete: int = 0
    subjects_pending: int = 0
    subjects_passed: int = 0
    subjects_failed: int = 0

    # None until every credit-bearing subject has a grade.
    sgpa: float | None = None
    overall_percent: float | None = None
    has_data: bool = False
    reason: str | None = None

    # Reported beside the result, never used to withhold it.
    attendance_percent: float | None = None
    attendance_threshold: float = RESULT_ATTENDANCE_FLAG_THRESHOLD
    attendance_short: bool = False

    generated_at: datetime | None = None


class GradeBand(BaseModel):
    """One bar of a grade distribution."""

    grade_letter: str
    grade_point: float
    min_percent: float
    student_count: int = 0
    percentage: float = 0.0


class SubjectResultReport(BaseModel):
    """A section's standing in one subject — the analysis screen."""

    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    credits: int | None = None

    section_id: int
    section_name: str | None = None
    section_code: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None
    teaching_assignment_id: int | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None

    allocated_weightage: float = 0.0
    assessments_total: int = 0
    assessments_counted: int = 0
    assessments_pending: int = 0

    total_students: int = 0
    graded_students: int = 0
    pending_students: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0

    average_percent: float | None = None
    highest_percent: float | None = None
    lowest_percent: float | None = None
    topper_student_id: int | None = None
    topper_student_name: str | None = None

    distribution: list[GradeBand] = []

    has_data: bool = False
    reason: str | None = None

    generated_at: datetime | None = None


class SectionResultRow(BaseModel):
    """One student's row on a section mark sheet."""

    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    student_status: str | None = None

    # subject_id -> percent, so the grid renders one column per subject.
    subject_percent: dict[int, float | None] = {}
    subject_grade: dict[int, str | None] = {}

    total_credits: int = 0
    earned_credits: int = 0
    subjects_passed: int = 0
    subjects_failed: int = 0
    subjects_pending: int = 0

    sgpa: float | None = None
    overall_percent: float | None = None
    has_data: bool = False


class SectionSubjectColumn(BaseModel):
    """One column header on a section mark sheet."""

    subject_id: int
    subject_code: str | None = None
    subject_name: str | None = None
    credits: int | None = None
    faculty_name: str | None = None
    allocated_weightage: float = 0.0
    assessments_pending: int = 0


class SectionResultReport(BaseModel):
    section_id: int
    section_name: str | None = None
    section_code: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None
    semester_number: int | None = None
    course_id: int | None = None
    course_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None

    as_of: date | None = None

    subjects: list[SectionSubjectColumn] = []
    students: list[SectionResultRow] = []

    total_students: int = 0
    complete_students: int = 0
    pending_students: int = 0
    pass_count: int = 0
    fail_count: int = 0
    pass_percentage: float = 0.0
    average_sgpa: float | None = None

    distribution: list[GradeBand] = []

    has_data: bool = False
    reason: str | None = None

    generated_at: datetime | None = None
