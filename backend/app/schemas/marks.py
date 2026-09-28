"""Marks — one student's standing in one assessment, and the sheet that holds
the whole roster.

The invariant this module exists to protect: **NULL is not zero**. A row whose
``marks_obtained`` is None is a student nobody has entered a mark for yet, and
an assessment with any such row is incomplete. Incomplete assessments are
excluded from result computation entirely rather than scoring the missing
students 0 — a zero for a skipped student is indistinguishable afterwards from
a real zero, and it fails them silently.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Drawn on the sheet against each entered mark, and counted in the header.
# ENTERED is any real mark; PENDING is the NULL above.
MarkRowState = Literal["PENDING", "ENTERED", "ABSENT", "MALPRACTICE"]

# Where a sheet stands overall.
#   EMPTY      - nothing entered
#   PARTIAL    - some entered, some still PENDING
#   COMPLETE   - every student on the roster accounted for
MarkSheetState = Literal["EMPTY", "PARTIAL", "COMPLETE"]


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------

class MarkEntry(BaseModel):
    """One cell of the sheet, as the client sends it back.

    ``marks_obtained`` may be None, and that is meaningful: it clears a mark
    back to "not entered" rather than writing a zero.
    """

    student_id: int = Field(..., gt=0)
    marks_obtained: float | None = Field(default=None, ge=0, le=1000)
    is_absent: bool = False
    is_malpractice: bool = False
    remarks: str | None = Field(default=None, max_length=500)


class MarkRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # None on a pending row — the student is on the roster but nothing is
    # saved for them yet.
    id: int | None = None
    assessment_id: int | None = None
    student_id: int
    section_id: int | None = None

    marks_obtained: float | None = None
    is_absent: bool = False
    is_malpractice: bool = False
    remarks: str | None = None

    entered_by_user_id: int | None = None
    entered_by_name: str | None = None
    entered_at: datetime | None = None

    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    student_code: str | None = None
    student_name: str | None = None
    student_email: str | None = None
    student_status: str | None = None
    student_section_id: int | None = None
    student_section_name: str | None = None

    # Derived, so the table renders without recomputing per cell.
    percent: float | None = None
    grade_letter: str | None = None
    is_pass: bool | None = None
    row_state: MarkRowState = "PENDING"

    # True when the mark was entered against a section the student has since
    # left — surfaces a mid-semester transfer instead of hiding it.
    moved_section: bool = False


# --------------------------------------------------------------------------
# the entry sheet
# --------------------------------------------------------------------------

class MarkSheetSave(BaseModel):
    assessment_id: int = Field(..., gt=0)
    entries: list[MarkEntry] = []


class MarkSheet(BaseModel):
    """Everything the marks-entry screen needs in one payload."""

    assessment_id: int
    records: list[MarkRecordOut] = []

    sheet_state: MarkSheetState = "EMPTY"
    editable: bool = True
    # Why the sheet refuses to accept marks: locked, not yours, inactive.
    locked_reason: str | None = None

    assessment_name: str | None = None
    assessment_type: str | None = None
    sequence_no: int | None = None
    status: str | None = None
    max_marks: float = 0.0
    pass_marks: float | None = None
    weightage_percent: float = 0.0
    scheduled_date: date | None = None

    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    section_code: str | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None

    total_students: int = 0
    entered_count: int = 0
    pending_count: int = 0
    absent_count: int = 0
    malpractice_count: int = 0
    pass_count: int = 0
    fail_count: int = 0

    # Over entered marks only.
    average_marks: float = 0.0
    average_percent: float = 0.0
    highest_marks: float | None = None
    lowest_marks: float | None = None


class PendingAssessmentOut(BaseModel):
    """One row in a faculty member's "what do I still have to enter" list.

    This is what makes the module usable: a lecturer opens the screen and sees
    their outstanding work, rather than an empty picker they must fill in
    before anything appears.
    """

    assessment_id: int
    teaching_assignment_id: int

    name: str
    assessment_type: str
    sequence_no: int
    status: str
    max_marks: float
    weightage_percent: float
    scheduled_date: date | None = None

    subject_id: int | None = None
    subject_code: str | None = None
    subject_name: str | None = None
    subject_type: str | None = None
    section_id: int | None = None
    section_name: str | None = None
    section_code: str | None = None
    faculty_id: int | None = None
    faculty_name: str | None = None
    semester_id: int | None = None
    semester_name: str | None = None

    total_students: int = 0
    entered_count: int = 0
    pending_count: int = 0
    completion_percent: float = 0.0

    editable: bool = True
    # PENDING while anything is unentered; COMPLETE once the roster is
    # accounted for; LOCKED wins over both, because the sheet will not open.
    state: Literal["PENDING", "COMPLETE", "LOCKED"] = "PENDING"
