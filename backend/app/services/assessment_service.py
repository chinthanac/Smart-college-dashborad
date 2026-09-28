"""Assessments — the gradable components of a subject.

An assessment is one component ("Internal 1", "Lab Exam") of one subject for
one section. It hangs off a teaching assignment, so who teaches what to whom is
settled before anything here runs and cannot be contradicted: the assessment
copies its whole identity from the assignment and accepts none of it from the
client, exactly as an attendance session copies its identity from a timetable
entry.

What this module owns:

  * that the components of one class never claim more than 100% between them —
    the sum of their weightages is the denominator of the subject's final
    percentage, so an overflow makes every result that subject produces
    quietly wrong, and a rejection therefore names what is already consuming
    the budget rather than saying "invalid";
  * that ``max_marks`` can never fall below a mark somebody has already been
    given, which would put a student above full marks;
  * that DRAFT reaches nobody — not a student, not a report, not a dashboard
    figure — so publishing is the deliberate act that makes a mark real;
  * that a LOCKED sheet refuses faculty writes, and that reopening one is an
    administrative act which leaves a trace;
  * that an assessment with marks on it is not casually deleted.

Entering the marks themselves belongs to ``marks_service``; turning them into
grades belongs to ``results_service``. Neither may relax a rule stated here.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.assessment import Assessment
from app.models.course import Course
from app.models.faculty import Faculty
from app.models.mark_record import MarkRecord
from app.models.section import Section
from app.models.semester import Semester
from app.models.student import Student
from app.models.subject import Subject
from app.models.teaching_assignment import TeachingAssignment
from app.models.user import User
from app.schemas.assessment import (
    ASSESSMENT_STATUSES,
    ASSESSMENT_TYPES,
    COUNTED_ASSESSMENT_STATUSES,
    DEFAULT_ASSESSMENT_STATUS,
    FROZEN_ASSESSMENT_STATUSES,
    GRADE_SCALE,
    MAX_TOTAL_WEIGHTAGE,
    PASS_PERCENT,
    RESULT_ATTENDANCE_FLAG_THRESHOLD,
    WEIGHTAGE_EPSILON,
    AssessmentCreate,
    AssessmentOptions,
    AssessmentOut,
    AssessmentStatusUpdate,
    AssessmentUpdate,
    WeightageBudget,
    WeightageConsumer,
    default_pass_marks,
)

ACTIVE_STUDENT_STATUS = "ACTIVE"

DUPLICATE_DETAIL = (
    "This class already has an assessment of that type with that number. "
    "Edit the existing one, or give this a different number."
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _faculty_name(faculty: Faculty | None) -> str | None:
    if not faculty:
        return None
    return f"{faculty.first_name} {faculty.last_name}".strip() or None


def _user_name(user: User | None) -> str | None:
    return user.name if user else None


def _round(value: float) -> float:
    return round(value + 0.0, 2)


# --------------------------------------------------------------------------
# options
# --------------------------------------------------------------------------

def options() -> AssessmentOptions:
    return AssessmentOptions(
        types=ASSESSMENT_TYPES,
        statuses=ASSESSMENT_STATUSES,
        counted_statuses=COUNTED_ASSESSMENT_STATUSES,
        default_status=DEFAULT_ASSESSMENT_STATUS,
        max_total_weightage=MAX_TOTAL_WEIGHTAGE,
        pass_percent=PASS_PERCENT,
        grade_scale=[
            {"min_percent": minimum, "letter": letter, "grade_point": point}
            for minimum, letter, point in GRADE_SCALE
        ],
        attendance_flag_threshold=RESULT_ATTENDANCE_FLAG_THRESHOLD,
    )


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def normalize_type(value: str) -> str:
    normalized = (value or "").strip().upper()
    if normalized not in ASSESSMENT_TYPES:
        raise _bad_request(
            f"Unknown assessment type '{value}'. Expected one of: {', '.join(ASSESSMENT_TYPES)}."
        )
    return normalized


def get_assignment_or_404(db: Session, assignment_id: int) -> TeachingAssignment:
    assignment = (
        db.query(TeachingAssignment)
        .options(
            joinedload(TeachingAssignment.subject),
            joinedload(TeachingAssignment.section),
            joinedload(TeachingAssignment.faculty),
        )
        .filter(TeachingAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise _not_found("Teaching assignment not found")
    return assignment


def validate_assignment_for_write(assignment: TeachingAssignment) -> None:
    """A paused class cannot take on new work.

    The assignment is deactivated when a lecturer goes on leave and the class
    is not running. Letting an assessment be created against it would put an
    exam on a class that nobody is teaching.
    """
    if not assignment.is_active:
        raise _bad_request(
            "This teaching assignment is paused. Reactivate it before adding assessments."
        )
    if assignment.subject and not assignment.subject.is_active:
        raise _bad_request("Subject is inactive and cannot take new assessments.")
    if assignment.section and not assignment.section.is_active:
        raise _bad_request("Section is inactive and cannot take new assessments.")


def ensure_unique_component(
    db: Session,
    assignment_id: int,
    assessment_type: str,
    sequence_no: int,
    exclude_id: int | None = None,
) -> None:
    """One "Internal 1" per class.

    Deliberately does not filter on is_active — the database constraint does
    not either, so an inactive row still occupies the slot.
    """
    query = db.query(Assessment).filter(
        Assessment.teaching_assignment_id == assignment_id,
        Assessment.assessment_type == assessment_type,
        Assessment.sequence_no == sequence_no,
    )
    if exclude_id is not None:
        query = query.filter(Assessment.id != exclude_id)
    if query.first():
        raise _conflict(DUPLICATE_DETAIL)


def resolve_pass_marks(pass_marks: float | None, max_marks: float) -> float:
    resolved = default_pass_marks(max_marks) if pass_marks is None else float(pass_marks)
    if resolved > max_marks:
        raise _bad_request(
            f"Pass mark ({_round(resolved)}) cannot exceed the maximum mark ({_round(max_marks)})."
        )
    return _round(resolved)


# --------------------------------------------------------------------------
# the weightage ledger
# --------------------------------------------------------------------------

def weightage_budget(
    db: Session,
    assignment: TeachingAssignment,
    exclude_id: int | None = None,
) -> WeightageBudget:
    """What is left of this class's 100%, and what has taken the rest.

    Inactive assessments are excluded: a component that has been switched off
    is not running, so it should not hold a share of the subject hostage.
    """
    query = db.query(Assessment).filter(
        Assessment.teaching_assignment_id == assignment.id,
        Assessment.is_active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(Assessment.id != exclude_id)

    siblings = query.order_by(Assessment.assessment_type.asc(), Assessment.sequence_no.asc()).all()
    allocated = sum(float(item.weightage_percent or 0.0) for item in siblings)
    remaining = MAX_TOTAL_WEIGHTAGE - allocated

    subject = assignment.subject
    section = assignment.section

    return WeightageBudget(
        teaching_assignment_id=assignment.id,
        subject_id=assignment.subject_id,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        section_id=assignment.section_id,
        section_name=section.name if section else None,
        max_total=MAX_TOTAL_WEIGHTAGE,
        allocated=_round(allocated),
        remaining=_round(max(remaining, 0.0)),
        is_fully_allocated=remaining <= WEIGHTAGE_EPSILON,
        consumers=[
            WeightageConsumer(
                assessment_id=item.id,
                name=item.name,
                assessment_type=item.assessment_type,
                weightage_percent=_round(float(item.weightage_percent or 0.0)),
                status=item.status,
            )
            for item in siblings
        ],
    )


def ensure_weightage_fits(
    db: Session,
    assignment: TeachingAssignment,
    requested: float,
    exclude_id: int | None = None,
) -> WeightageBudget:
    """Reject an overflow by name.

    "Internal 1 (30%) and Assignment 1 (20%) already allocate 50% of CS301 /
    Section A. 50% remains, but 60% was requested." A bare "invalid weightage"
    makes the user guess which of their components to shrink.
    """
    budget = weightage_budget(db, assignment, exclude_id=exclude_id)
    if requested <= budget.remaining + WEIGHTAGE_EPSILON:
        return budget

    subject = assignment.subject
    section = assignment.section
    label = " / ".join(
        part
        for part in (
            subject.subject_code if subject else None,
            section.name if section else None,
        )
        if part
    ) or "this class"

    if budget.consumers:
        consumed = ", ".join(
            f"{item.name} ({_round(item.weightage_percent)}%)" for item in budget.consumers
        )
        detail = (
            f"{consumed} already allocate {_round(budget.allocated)}% of {label}. "
            f"{_round(budget.remaining)}% remains, but {_round(requested)}% was requested."
        )
    else:
        detail = (
            f"{label} can allocate at most {_round(MAX_TOTAL_WEIGHTAGE)}%, "
            f"but {_round(requested)}% was requested."
        )
    raise _bad_request(detail)


# --------------------------------------------------------------------------
# permissions
# --------------------------------------------------------------------------

def faculty_for_user(db: Session, current_user: User) -> Faculty:
    faculty = db.query(Faculty).filter(Faculty.user_id == current_user.id).first()
    if not faculty:
        raise _forbidden("No faculty profile is linked to this account.")
    return faculty


def ensure_can_manage_assignment(
    db: Session,
    current_user: User,
    assignment: TeachingAssignment,
) -> None:
    """Admins manage any class; faculty only the classes they teach."""
    if current_user.role == "ADMIN":
        return
    faculty = faculty_for_user(db, current_user)
    if assignment.faculty_id != faculty.id:
        raise _forbidden("You can only manage assessments for the classes you teach.")


def is_frozen(assessment: Assessment) -> bool:
    return (assessment.status or "").upper() in FROZEN_ASSESSMENT_STATUSES


def counts_toward_result(assessment: Assessment) -> bool:
    return bool(assessment.is_active) and (assessment.status or "").upper() in COUNTED_ASSESSMENT_STATUSES


def ensure_writable(db: Session, current_user: User, assessment: Assessment) -> None:
    """The gate every write on an existing assessment passes through.

    An admin may correct a locked sheet — that is the whole point of the
    admin unlock — so the freeze applies to faculty only.
    """
    ensure_can_manage_assignment(db, current_user, assessment.teaching_assignment)
    if current_user.role != "ADMIN" and is_frozen(assessment):
        raise _forbidden(
            f"'{assessment.name}' is locked. Ask an administrator to unlock it before editing."
        )


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def _roster_counts(db: Session, section_ids: list[int]) -> dict[int, int]:
    """ACTIVE students per section — the denominator of entry progress."""
    if not section_ids:
        return {}
    rows = (
        db.query(Student.section_id, Student.id)
        .filter(
            Student.section_id.in_(set(section_ids)),
            Student.status == ACTIVE_STUDENT_STATUS,
        )
        .all()
    )
    counts: dict[int, int] = {}
    for section_id, _ in rows:
        counts[section_id] = counts.get(section_id, 0) + 1
    return counts


def _blank_stats() -> dict:
    return {
        "entered": 0,
        "absent": 0,
        "malpractice": 0,
        "marks": [],
        "pass": 0,
        "fail": 0,
    }


def _record_stats(db: Session, assessment_ids: list[int]) -> dict[int, dict]:
    """One query for every assessment on the page, not one per row."""
    if not assessment_ids:
        return {}

    records = (
        db.query(MarkRecord)
        .filter(MarkRecord.assessment_id.in_(set(assessment_ids)))
        .all()
    )

    stats: dict[int, dict] = {}
    for record in records:
        bucket = stats.setdefault(record.assessment_id, _blank_stats())
        if record.is_malpractice:
            bucket["malpractice"] += 1
            bucket["entered"] += 1
        elif record.is_absent:
            bucket["absent"] += 1
            bucket["entered"] += 1
        elif record.marks_obtained is not None:
            bucket["entered"] += 1
            bucket["marks"].append(float(record.marks_obtained))
        # marks_obtained is None and neither flag set: not entered. It is
        # deliberately NOT counted as a zero.
    return stats


def _apply_stats(out: AssessmentOut, assessment: Assessment, stats: dict, roster_total: int) -> None:
    marks = stats["marks"]
    entered = stats["entered"]
    absent = stats["absent"] + stats["malpractice"]

    pass_mark = assessment.pass_marks
    if pass_mark is None:
        pass_mark = default_pass_marks(float(assessment.max_marks or 0.0))

    passed = sum(1 for value in marks if value >= pass_mark)
    # An absentee and a malpractice case have not passed. They are counted
    # here and reported separately above, so neither statistic hides the other.
    failed = (entered - passed) if entered else 0

    out.total_students = roster_total
    out.entered_count = entered
    out.pending_count = max(roster_total - entered, 0)
    out.absent_count = absent
    out.is_complete = roster_total > 0 and entered >= roster_total

    out.pass_count = passed
    out.fail_count = max(failed, 0)

    if marks:
        out.average_marks = _round(sum(marks) / len(marks))
        out.highest_marks = _round(max(marks))
        out.lowest_marks = _round(min(marks))
        if assessment.max_marks:
            out.average_percent = _round(out.average_marks * 100.0 / float(assessment.max_marks))


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize(
    assessment: Assessment,
    stats: dict | None = None,
    roster_total: int = 0,
    current_user: User | None = None,
) -> AssessmentOut:
    subject = assessment.subject
    section = assessment.section
    semester = assessment.semester
    faculty = assessment.faculty
    course = subject.course if subject else None
    department = course.department if course else None
    academic_year = semester.academic_year if semester else None

    editable = not is_frozen(assessment)
    if current_user is not None and current_user.role == "ADMIN":
        editable = True

    out = AssessmentOut(
        id=assessment.id,
        teaching_assignment_id=assessment.teaching_assignment_id,
        faculty_id=assessment.faculty_id,
        subject_id=assessment.subject_id,
        section_id=assessment.section_id,
        semester_id=assessment.semester_id,
        assessment_type=assessment.assessment_type,
        name=assessment.name,
        sequence_no=assessment.sequence_no,
        description=assessment.description,
        max_marks=float(assessment.max_marks or 0.0),
        weightage_percent=float(assessment.weightage_percent or 0.0),
        pass_marks=float(assessment.pass_marks) if assessment.pass_marks is not None else None,
        scheduled_date=assessment.scheduled_date,
        duration_minutes=assessment.duration_minutes,
        status=assessment.status,
        created_by_user_id=assessment.created_by_user_id,
        published_at=assessment.published_at,
        locked_by_user_id=assessment.locked_by_user_id,
        locked_at=assessment.locked_at,
        is_active=assessment.is_active,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        subject_credits=subject.credits if subject else None,
        faculty_name=_faculty_name(faculty),
        faculty_code=faculty.faculty_id if faculty else None,
        faculty_department_id=faculty.department_id if faculty else None,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=course.id if course else None,
        course_name=course.name if course else None,
        course_code=course.code if course else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        academic_year_id=academic_year.id if academic_year else None,
        academic_year_name=academic_year.name if academic_year else None,
        created_by_name=_user_name(assessment.created_by),
        locked_by_name=_user_name(assessment.locked_by),
        editable_by_faculty=editable,
        counts_toward_result=counts_toward_result(assessment),
    )

    _apply_stats(out, assessment, stats or _blank_stats(), roster_total)
    return out


def serialize_many(
    db: Session,
    assessments: list[Assessment],
    current_user: User | None = None,
) -> list[AssessmentOut]:
    stats = _record_stats(db, [item.id for item in assessments])
    rosters = _roster_counts(db, [item.section_id for item in assessments])
    return [
        serialize(
            item,
            stats=stats.get(item.id, _blank_stats()),
            roster_total=rosters.get(item.section_id, 0),
            current_user=current_user,
        )
        for item in assessments
    ]


def serialize_one(db: Session, assessment: Assessment, current_user: User | None = None) -> AssessmentOut:
    return serialize_many(db, [assessment], current_user=current_user)[0]


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def _base_query(db: Session):
    return (
        db.query(Assessment)
        .join(Subject, Assessment.subject_id == Subject.id)
        .join(Section, Assessment.section_id == Section.id)
        .join(Course, Subject.course_id == Course.id)
        .join(Semester, Assessment.semester_id == Semester.id)
        .options(
            joinedload(Assessment.subject).joinedload(Subject.course),
            joinedload(Assessment.section),
            joinedload(Assessment.semester),
            joinedload(Assessment.faculty),
            joinedload(Assessment.teaching_assignment),
            joinedload(Assessment.created_by),
            joinedload(Assessment.locked_by),
        )
    )


def list_assessments(
    db: Session,
    teaching_assignment_id: int | None = None,
    faculty_id: int | None = None,
    subject_id: int | None = None,
    section_id: int | None = None,
    semester_id: int | None = None,
    course_id: int | None = None,
    department_id: int | None = None,
    academic_year_id: int | None = None,
    assessment_type: str | None = None,
    status: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[Assessment]:
    query = _base_query(db)

    if teaching_assignment_id is not None:
        query = query.filter(Assessment.teaching_assignment_id == teaching_assignment_id)
    if faculty_id is not None:
        query = query.filter(Assessment.faculty_id == faculty_id)
    if subject_id is not None:
        query = query.filter(Assessment.subject_id == subject_id)
    if section_id is not None:
        query = query.filter(Assessment.section_id == section_id)
    if semester_id is not None:
        query = query.filter(Assessment.semester_id == semester_id)
    if course_id is not None:
        query = query.filter(Subject.course_id == course_id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if assessment_type is not None:
        query = query.filter(Assessment.assessment_type == normalize_type(assessment_type))
    if status is not None:
        query = query.filter(Assessment.status == status.strip().upper())
    if is_active is not None:
        query = query.filter(Assessment.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Assessment.name.ilike(term)
            | Subject.subject_code.ilike(term)
            | Subject.name.ilike(term)
            | Section.name.ilike(term)
            | Section.code.ilike(term)
        )

    return query.order_by(
        Subject.subject_code.asc(),
        Section.name.asc(),
        Assessment.assessment_type.asc(),
        Assessment.sequence_no.asc(),
        Assessment.id.asc(),
    ).all()


def get_assessment_or_404(db: Session, assessment_id: int) -> Assessment:
    assessment = _base_query(db).filter(Assessment.id == assessment_id).first()
    if not assessment:
        raise _not_found("Assessment not found")
    return assessment


def count_for_assignment(db: Session, assignment_id: int) -> int:
    return (
        db.query(Assessment)
        .filter(Assessment.teaching_assignment_id == assignment_id)
        .count()
    )


def count_for_section(db: Session, section_id: int) -> int:
    return db.query(Assessment).filter(Assessment.section_id == section_id).count()


def count_for_subject(db: Session, subject_id: int) -> int:
    return db.query(Assessment).filter(Assessment.subject_id == subject_id).count()


def count_marks(db: Session, assessment_id: int) -> int:
    return db.query(MarkRecord).filter(MarkRecord.assessment_id == assessment_id).count()


def highest_mark(db: Session, assessment_id: int) -> float | None:
    values = [
        float(value)
        for (value,) in db.query(MarkRecord.marks_obtained)
        .filter(
            MarkRecord.assessment_id == assessment_id,
            MarkRecord.marks_obtained.isnot(None),
        )
        .all()
    ]
    return max(values) if values else None


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_assessment(db: Session, current_user: User, payload: AssessmentCreate) -> Assessment:
    assignment = get_assignment_or_404(db, payload.teaching_assignment_id)
    ensure_can_manage_assignment(db, current_user, assignment)
    validate_assignment_for_write(assignment)

    assessment_type = normalize_type(payload.assessment_type)
    name = (payload.name or "").strip()
    if not name:
        raise _bad_request("Assessment name is required.")

    ensure_unique_component(db, assignment.id, assessment_type, payload.sequence_no)
    ensure_weightage_fits(db, assignment, float(payload.weightage_percent))
    pass_marks = resolve_pass_marks(payload.pass_marks, float(payload.max_marks))

    assessment = Assessment(
        teaching_assignment_id=assignment.id,
        # Copied from the assignment, never from the client.
        faculty_id=assignment.faculty_id,
        subject_id=assignment.subject_id,
        section_id=assignment.section_id,
        semester_id=assignment.semester_id,
        assessment_type=assessment_type,
        name=name,
        sequence_no=payload.sequence_no,
        description=(payload.description or "").strip() or None,
        max_marks=_round(float(payload.max_marks)),
        weightage_percent=_round(float(payload.weightage_percent)),
        pass_marks=pass_marks,
        scheduled_date=payload.scheduled_date,
        duration_minutes=payload.duration_minutes,
        status=DEFAULT_ASSESSMENT_STATUS,
        created_by_user_id=current_user.id,
        is_active=True,
    )

    try:
        db.add(assessment)
        db.commit()
    except IntegrityError:
        # The unique constraint can still fire if somebody wrote the same
        # component between the check above and this commit.
        db.rollback()
        raise _conflict(DUPLICATE_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the assessment. Please try again.")

    db.refresh(assessment)
    return assessment


def update_assessment(
    db: Session,
    current_user: User,
    assessment: Assessment,
    payload: AssessmentUpdate,
) -> Assessment:
    ensure_writable(db, current_user, assessment)
    assignment = assessment.teaching_assignment

    data = payload.model_dump(exclude_unset=True)

    assessment_type = (
        normalize_type(data["assessment_type"])
        if "assessment_type" in data and data["assessment_type"] is not None
        else assessment.assessment_type
    )
    sequence_no = data.get("sequence_no") or assessment.sequence_no
    if assessment_type != assessment.assessment_type or sequence_no != assessment.sequence_no:
        ensure_unique_component(
            db, assignment.id, assessment_type, sequence_no, exclude_id=assessment.id
        )

    max_marks = float(data.get("max_marks") or assessment.max_marks)
    if "max_marks" in data and data["max_marks"] is not None:
        # Lowering the ceiling under a mark already awarded would put that
        # student above full marks, and every percentage they have would be
        # over 100. Name the mark that blocks it.
        highest = highest_mark(db, assessment.id)
        if highest is not None and max_marks < highest:
            raise _bad_request(
                f"A mark of {_round(highest)} has already been awarded, so the maximum "
                f"cannot be lowered to {_round(max_marks)}. Correct that mark first."
            )

    if "weightage_percent" in data and data["weightage_percent"] is not None:
        ensure_weightage_fits(
            db, assignment, float(data["weightage_percent"]), exclude_id=assessment.id
        )

    # Re-resolve whenever either side of the relationship moves, so an
    # unset pass mark tracks a changed maximum instead of going stale.
    if "pass_marks" in data or "max_marks" in data:
        pass_marks = resolve_pass_marks(data.get("pass_marks"), max_marks)
    else:
        pass_marks = assessment.pass_marks

    if "name" in data and data["name"] is not None:
        name = data["name"].strip()
        if not name:
            raise _bad_request("Assessment name is required.")
        assessment.name = name

    try:
        assessment.assessment_type = assessment_type
        assessment.sequence_no = sequence_no
        if "description" in data:
            assessment.description = (data["description"] or "").strip() or None
        assessment.max_marks = _round(max_marks)
        if "weightage_percent" in data and data["weightage_percent"] is not None:
            assessment.weightage_percent = _round(float(data["weightage_percent"]))
        assessment.pass_marks = pass_marks
        if "scheduled_date" in data:
            assessment.scheduled_date = data["scheduled_date"]
        if "duration_minutes" in data:
            assessment.duration_minutes = data["duration_minutes"]
        if "is_active" in data and data["is_active"] is not None:
            assessment.is_active = bool(data["is_active"])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(DUPLICATE_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the assessment. Please try again.")

    db.refresh(assessment)
    return assessment


def set_status(
    db: Session,
    current_user: User,
    assessment: Assessment,
    payload: AssessmentStatusUpdate,
) -> Assessment:
    """publish / lock / unlock.

    Publishing is what makes marks real, so it is refused on an assessment
    nobody has entered anything for: a published component with no marks
    contributes an empty column to every result it touches and looks like a
    system fault rather than an empty sheet.
    """
    action = payload.action
    current = (assessment.status or "").upper()
    ensure_can_manage_assignment(db, current_user, assessment.teaching_assignment)

    if action == "publish":
        if current == "PUBLISHED":
            raise _bad_request(f"'{assessment.name}' is already published.")
        if current == "LOCKED":
            raise _bad_request(
                f"'{assessment.name}' is locked. Unlock it first if you need to change it."
            )
        if not assessment.is_active:
            raise _bad_request("An inactive assessment cannot be published.")
        if count_marks(db, assessment.id) == 0:
            raise _bad_request(
                f"No marks have been entered for '{assessment.name}', so there is "
                "nothing to publish."
            )
        assessment.status = "PUBLISHED"
        assessment.published_at = _now()

    elif action == "lock":
        if current == "LOCKED":
            raise _bad_request(f"'{assessment.name}' is already locked.")
        if current != "PUBLISHED":
            raise _bad_request(
                f"'{assessment.name}' must be published before it can be locked."
            )
        assessment.status = "LOCKED"
        assessment.locked_by_user_id = current_user.id
        assessment.locked_at = _now()

    elif action == "unlock":
        # Reopening a frozen sheet is an administrative act, and the lock
        # stamp is deliberately left in place so the row still shows that it
        # was locked, by whom and when.
        if current_user.role != "ADMIN":
            raise _forbidden("Only an administrator can unlock an assessment.")
        if current != "LOCKED":
            raise _bad_request(f"'{assessment.name}' is not locked.")
        assessment.status = "PUBLISHED"

    else:  # pragma: no cover - Literal in the schema forbids it
        raise _bad_request(f"Unknown action '{action}'.")

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not change the assessment status. Please try again.")

    db.refresh(assessment)
    return assessment


def delete_assessment(
    db: Session,
    current_user: User,
    assessment: Assessment,
    force: bool = False,
) -> None:
    """Hard delete, and it takes the marks with it.

    The count is stated before the fact rather than after, because "deleted 52
    mark records" is not a useful thing to learn from a success message.
    """
    if current_user.role != "ADMIN":
        raise _forbidden("Only an administrator can delete an assessment.")

    marked = count_marks(db, assessment.id)
    if marked and not force:
        raise _conflict(
            f"'{assessment.name}' has {marked} mark record(s) on file. Deactivate it "
            "instead, or confirm the deletion to discard those marks."
        )

    try:
        db.delete(assessment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the assessment. Please try again.")
