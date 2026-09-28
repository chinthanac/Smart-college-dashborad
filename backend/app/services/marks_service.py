"""Marks entry — the sheet, and what may be written into it.

One rule sits under everything here: **a missing mark is not a zero.**

"Not entered" is represented by the *absence* of a row, never by a row holding
zero and never by a row holding NULL with no reason attached. A row exists only
once somebody has said something about that student — a mark, an absence, or a
malpractice case. Clearing a mark therefore removes the row and returns the
student to pending, which keeps "we do not know" expressible in exactly one
way. ``results_service`` reads that single representation and excludes an
incomplete component rather than failing the students nobody got to.

The other rules:

  * a mark is bounded by the assessment's own ``max_marks`` — a value above it
    would put the student over 100% in every percentage they appear in;
  * an absence and a malpractice case carry no mark, and both are reported as
    their own counts, because "twelve absentees" and "twelve zeros" are
    different facts about a class;
  * the sheet is built from the section's ACTIVE students, while nothing that
    reads saved marks filters on status — a student suspended in November
    keeps the marks they earned in October;
  * saving corrects the sheet rather than duplicating it, and the whole
    payload is validated before a single row is written, so a sheet of fifty
    students never lands half-applied.

What may be graded at all is settled by ``assessment_service`` and cannot be
relaxed here.
"""

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from app.models.assessment import Assessment
from app.models.mark_record import MarkRecord
from app.models.student import Student
from app.models.user import User
from app.schemas.assessment import default_pass_marks, grade_for
from app.schemas.marks import (
    MarkRecordOut,
    MarkSheet,
    MarkSheetSave,
    PendingAssessmentOut,
)
from app.services import assessment_service
from app.services.assessment_service import (
    _bad_request,
    _conflict,
    _forbidden,
    _round,
)

ACTIVE_STUDENT_STATUS = "ACTIVE"


def _student_name(student: Student | None) -> str | None:
    if not student:
        return None
    return f"{student.first_name} {student.last_name}".strip() or None


def _effective_marks(record: MarkRecord) -> float:
    """What the mark counts as. An absence and a malpractice case count as 0."""
    if record.is_absent or record.is_malpractice:
        return 0.0
    return float(record.marks_obtained or 0.0)


def pass_mark_for(assessment: Assessment) -> float:
    if assessment.pass_marks is not None:
        return float(assessment.pass_marks)
    return default_pass_marks(float(assessment.max_marks or 0.0))


# --------------------------------------------------------------------------
# access
# --------------------------------------------------------------------------

def get_assessment_or_404(db: Session, assessment_id: int) -> Assessment:
    return assessment_service.get_assessment_or_404(db, assessment_id)


def entry_block_reason(db: Session, user: User, assessment: Assessment) -> str | None:
    """Why this sheet will not accept marks, phrased for the person reading it.

    Returns None when it will. Used both to gate a save and to render the
    sheet read-only, so the screen and the API never disagree about whether
    the fields should be typeable.
    """
    if not assessment.is_active:
        return f"'{assessment.name}' is inactive. Reactivate it before entering marks."

    if user.role == "ADMIN":
        return None

    try:
        assessment_service.ensure_can_manage_assignment(db, user, assessment.teaching_assignment)
    except Exception:
        return "You can only enter marks for the classes you teach."

    if assessment_service.is_frozen(assessment):
        return f"'{assessment.name}' is locked. Ask an administrator to unlock it."

    return None


def ensure_can_enter(db: Session, user: User, assessment: Assessment) -> None:
    # Ownership first, so somebody else's locked sheet reports "not yours"
    # rather than telling them how to get it unlocked.
    assessment_service.ensure_can_manage_assignment(db, user, assessment.teaching_assignment)

    if not assessment.is_active:
        raise _bad_request(
            f"'{assessment.name}' is inactive. Reactivate it before entering marks."
        )
    if user.role != "ADMIN" and assessment_service.is_frozen(assessment):
        raise _forbidden(
            f"'{assessment.name}' is locked. Ask an administrator to unlock it before "
            "entering marks."
        )


def ensure_can_view(db: Session, user: User, assessment: Assessment) -> None:
    if user.role == "ADMIN":
        return
    faculty = assessment_service.faculty_for_user(db, user)
    if assessment.faculty_id == faculty.id:
        return
    subject = assessment.subject
    course = subject.course if subject else None
    if course and course.department_id == faculty.department_id:
        return
    raise _forbidden("You can only view mark sheets from your own department.")


# --------------------------------------------------------------------------
# the roster
# --------------------------------------------------------------------------

def roster_for_assessment(db: Session, assessment: Assessment) -> list[Student]:
    """The section's ACTIVE students, in roll-number order.

    Only ever used to BUILD a sheet. Nothing that reads saved marks filters on
    status, or a student suspended later would lose the marks they had already
    earned.
    """
    from app.services import student_service

    return student_service.list_students(
        db, section_id=assessment.section_id, student_status=ACTIVE_STUDENT_STATUS
    )


def _records_for(db: Session, assessment_id: int) -> list[MarkRecord]:
    return (
        db.query(MarkRecord)
        .options(joinedload(MarkRecord.student), joinedload(MarkRecord.entered_by))
        .filter(MarkRecord.assessment_id == assessment_id)
        .all()
    )


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize_record(record: MarkRecord, assessment: Assessment) -> MarkRecordOut:
    student = record.student
    max_marks = float(assessment.max_marks or 0.0)
    pass_mark = pass_mark_for(assessment)

    if record.is_malpractice:
        row_state = "MALPRACTICE"
    elif record.is_absent:
        row_state = "ABSENT"
    else:
        row_state = "ENTERED"

    percent = None
    grade_letter = None
    if record.marks_obtained is not None and max_marks:
        percent = _round(float(record.marks_obtained) * 100.0 / max_marks)
        grade_letter, _ = grade_for(percent)

    return MarkRecordOut(
        id=record.id,
        assessment_id=record.assessment_id,
        student_id=record.student_id,
        section_id=record.section_id,
        marks_obtained=float(record.marks_obtained) if record.marks_obtained is not None else None,
        is_absent=bool(record.is_absent),
        is_malpractice=bool(record.is_malpractice),
        remarks=record.remarks,
        entered_by_user_id=record.entered_by_user_id,
        entered_by_name=record.entered_by.name if record.entered_by else None,
        entered_at=record.entered_at,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
        student_code=student.student_id if student else None,
        student_name=_student_name(student),
        student_email=student.user.email if student and student.user else None,
        student_status=student.status if student else None,
        student_section_id=student.section_id if student else None,
        student_section_name=student.section.name if student and student.section else None,
        percent=percent,
        grade_letter=grade_letter,
        is_pass=_effective_marks(record) >= pass_mark,
        row_state=row_state,
        moved_section=bool(student and student.section_id != record.section_id),
    )


def pending_record(student: Student) -> MarkRecordOut:
    """A student on the roster with nothing saved for them yet.

    Every derived field stays None. A zero here would be indistinguishable
    from a real zero the moment it reached a report.
    """
    return MarkRecordOut(
        student_id=student.id,
        section_id=student.section_id,
        marks_obtained=None,
        student_code=student.student_id,
        student_name=_student_name(student),
        student_email=student.user.email if student.user else None,
        student_status=student.status,
        student_section_id=student.section_id,
        student_section_name=student.section.name if student.section else None,
        percent=None,
        grade_letter=None,
        is_pass=None,
        row_state="PENDING",
    )


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------

def build_sheet(db: Session, user: User, assessment_id: int) -> MarkSheet:
    """Read-only. Opening a sheet never writes anything."""
    assessment = get_assessment_or_404(db, assessment_id)
    ensure_can_view(db, user, assessment)

    roster = roster_for_assessment(db, assessment)
    saved = {record.student_id: record for record in _records_for(db, assessment.id)}

    rows: list[MarkRecordOut] = []
    seen: set[int] = set()
    for student in roster:
        seen.add(student.id)
        record = saved.get(student.id)
        rows.append(serialize_record(record, assessment) if record else pending_record(student))

    # Anyone holding a mark who has since left the roster still appears, so a
    # transfer or a suspension never hides a mark that was actually awarded.
    for student_id, record in saved.items():
        if student_id not in seen:
            rows.append(serialize_record(record, assessment))

    subject = assessment.subject
    section = assessment.section
    semester = assessment.semester
    faculty = assessment.faculty

    sheet = MarkSheet(
        assessment_id=assessment.id,
        records=rows,
        locked_reason=entry_block_reason(db, user, assessment),
        assessment_name=assessment.name,
        assessment_type=assessment.assessment_type,
        sequence_no=assessment.sequence_no,
        status=assessment.status,
        max_marks=float(assessment.max_marks or 0.0),
        pass_marks=pass_mark_for(assessment),
        weightage_percent=float(assessment.weightage_percent or 0.0),
        scheduled_date=assessment.scheduled_date,
        subject_id=assessment.subject_id,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        section_id=assessment.section_id,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        faculty_id=assessment.faculty_id,
        faculty_name=assessment_service._faculty_name(faculty),
        semester_id=assessment.semester_id,
        semester_name=semester.name if semester else None,
    )
    sheet.editable = sheet.locked_reason is None

    _apply_sheet_totals(sheet, len(roster))
    return sheet


def _apply_sheet_totals(sheet: MarkSheet, roster_total: int) -> None:
    marks = [
        row.marks_obtained
        for row in sheet.records
        if row.marks_obtained is not None and not row.is_absent and not row.is_malpractice
    ]
    entered = [row for row in sheet.records if row.row_state != "PENDING"]

    sheet.total_students = roster_total
    sheet.entered_count = len(entered)
    sheet.pending_count = max(roster_total - len(entered), 0)
    sheet.absent_count = sum(1 for row in sheet.records if row.row_state == "ABSENT")
    sheet.malpractice_count = sum(1 for row in sheet.records if row.row_state == "MALPRACTICE")
    sheet.pass_count = sum(1 for row in entered if row.is_pass)
    sheet.fail_count = len(entered) - sheet.pass_count

    if marks:
        sheet.average_marks = _round(sum(marks) / len(marks))
        sheet.highest_marks = _round(max(marks))
        sheet.lowest_marks = _round(min(marks))
        if sheet.max_marks:
            sheet.average_percent = _round(sheet.average_marks * 100.0 / sheet.max_marks)

    if not entered:
        sheet.sheet_state = "EMPTY"
    elif roster_total and len(entered) >= roster_total:
        sheet.sheet_state = "COMPLETE"
    else:
        sheet.sheet_state = "PARTIAL"


# --------------------------------------------------------------------------
# saving
# --------------------------------------------------------------------------

def save_sheet(db: Session, user: User, payload: MarkSheetSave) -> Assessment:
    """Create or correct the marks on one assessment.

    All-or-nothing: the whole payload is validated before anything is written,
    so a rejected cell never leaves half a class graded. Entries the client
    omits are left untouched, which is what makes entering a sheet in several
    sittings safe.
    """
    assessment = get_assessment_or_404(db, payload.assessment_id)
    ensure_can_enter(db, user, assessment)

    max_marks = float(assessment.max_marks or 0.0)
    section = assessment.section

    # The roster, plus anyone already holding a mark — so a student who has
    # since gone INACTIVE can still have their existing row corrected.
    markable = {student.id: student for student in roster_for_assessment(db, assessment)}
    existing = {record.student_id: record for record in _records_for(db, assessment.id)}
    for student_id, record in existing.items():
        if record.student and student_id not in markable:
            markable[student_id] = record.student

    cleaned: list[tuple[Student, float | None, bool, bool, str | None]] = []
    seen: set[int] = set()

    for item in payload.entries:
        student = markable.get(item.student_id)
        if not student:
            raise _bad_request(
                f"Student {item.student_id} is not in "
                f"{section.name if section else 'this section'}."
            )
        if item.student_id in seen:
            raise _bad_request(f"{_student_name(student)} appears twice on this sheet.")
        seen.add(item.student_id)

        name = _student_name(student) or f"Student {item.student_id}"

        if item.is_absent and item.is_malpractice:
            raise _bad_request(
                f"{name} cannot be marked absent and a malpractice case at once."
            )

        if (item.is_absent or item.is_malpractice) and item.marks_obtained is not None:
            label = "absent" if item.is_absent else "a malpractice case"
            raise _bad_request(
                f"{name} is marked {label}, so no mark can be recorded. "
                "Clear the mark first."
            )

        if item.marks_obtained is not None and item.marks_obtained > max_marks:
            raise _bad_request(
                f"{name} scored {_round(float(item.marks_obtained))}, but "
                f"'{assessment.name}' is out of {_round(max_marks)}."
            )

        cleaned.append(
            (
                student,
                _round(float(item.marks_obtained)) if item.marks_obtained is not None else None,
                bool(item.is_absent),
                bool(item.is_malpractice),
                (item.remarks or "").strip() or None,
            )
        )

    try:
        for student, marks, is_absent, is_malpractice, remarks in cleaned:
            record = existing.get(student.id)

            if marks is None and not is_absent and not is_malpractice:
                # Nothing is being said about this student any more. The row
                # goes, and they return to pending — "not entered" has exactly
                # one representation, and it is the absence of a row.
                if record:
                    db.delete(record)
                continue

            if record:
                record.marks_obtained = marks
                record.is_absent = is_absent
                record.is_malpractice = is_malpractice
                record.remarks = remarks
                record.entered_by_user_id = user.id
                record.entered_at = func.now()
                # The section they sat in on the day this was entered.
                record.section_id = student.section_id
            else:
                db.add(
                    MarkRecord(
                        assessment_id=assessment.id,
                        student_id=student.id,
                        section_id=student.section_id,
                        marks_obtained=marks,
                        is_absent=is_absent,
                        is_malpractice=is_malpractice,
                        remarks=remarks,
                        entered_by_user_id=user.id,
                    )
                )

        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(
            f"Marks for '{assessment.name}' were just saved by someone else. "
            "Reload the sheet and try again."
        )
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not save the marks. Please try again.")

    db.refresh(assessment)
    return assessment


# --------------------------------------------------------------------------
# "what do I still have to enter"
# --------------------------------------------------------------------------

def list_pending_for_faculty(
    db: Session,
    user: User,
    semester_id: int | None = None,
    section_id: int | None = None,
    only_pending: bool = False,
) -> list[PendingAssessmentOut]:
    """A lecturer's outstanding marks entry, with progress on every row.

    The faculty id comes from the token, never a query parameter, so this
    cannot be pointed at somebody else's classes.
    """
    faculty = assessment_service.faculty_for_user(db, user)
    assessments = assessment_service.list_assessments(
        db,
        faculty_id=faculty.id,
        semester_id=semester_id,
        section_id=section_id,
        is_active=True,
    )

    stats = assessment_service._record_stats(db, [item.id for item in assessments])
    rosters = assessment_service._roster_counts(db, [item.section_id for item in assessments])

    rows: list[PendingAssessmentOut] = []
    for assessment in assessments:
        bucket = stats.get(assessment.id, assessment_service._blank_stats())
        total = rosters.get(assessment.section_id, 0)
        entered = bucket["entered"]
        pending = max(total - entered, 0)

        frozen = assessment_service.is_frozen(assessment)
        if frozen:
            state = "LOCKED"
        elif total and entered >= total:
            state = "COMPLETE"
        else:
            state = "PENDING"

        if only_pending and state != "PENDING":
            continue

        subject = assessment.subject
        section = assessment.section
        semester = assessment.semester

        rows.append(
            PendingAssessmentOut(
                assessment_id=assessment.id,
                teaching_assignment_id=assessment.teaching_assignment_id,
                name=assessment.name,
                assessment_type=assessment.assessment_type,
                sequence_no=assessment.sequence_no,
                status=assessment.status,
                max_marks=float(assessment.max_marks or 0.0),
                weightage_percent=float(assessment.weightage_percent or 0.0),
                scheduled_date=assessment.scheduled_date,
                subject_id=assessment.subject_id,
                subject_code=subject.subject_code if subject else None,
                subject_name=subject.name if subject else None,
                subject_type=subject.subject_type if subject else None,
                section_id=assessment.section_id,
                section_name=section.name if section else None,
                section_code=section.code if section else None,
                faculty_id=assessment.faculty_id,
                faculty_name=assessment_service._faculty_name(assessment.faculty),
                semester_id=assessment.semester_id,
                semester_name=semester.name if semester else None,
                total_students=total,
                entered_count=entered,
                pending_count=pending,
                completion_percent=_round(entered * 100.0 / total) if total else 0.0,
                editable=not frozen,
                state=state,
            )
        )

    # Outstanding work first — that is what the screen is for.
    order = {"PENDING": 0, "COMPLETE": 1, "LOCKED": 2}
    rows.sort(key=lambda row: (order.get(row.state, 3), row.subject_code or "", row.sequence_no))
    return rows


# --------------------------------------------------------------------------
# counts, for the guards other modules run before deleting
# --------------------------------------------------------------------------

def count_for_student(db: Session, student_id: int) -> int:
    return db.query(MarkRecord).filter(MarkRecord.student_id == student_id).count()


def count_for_section(db: Session, section_id: int) -> int:
    return db.query(MarkRecord).filter(MarkRecord.section_id == section_id).count()
