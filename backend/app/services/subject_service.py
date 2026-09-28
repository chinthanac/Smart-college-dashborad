"""Subject CRUD service.

Holds every subject rule: the Course → Semester relationship check, the
uniqueness of the subject code, and the credit/hour bounds. The router
stays thin.
"""

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.semester import Semester
from app.models.subject import Subject
from app.schemas.subject import SUBJECT_TYPES, SubjectCreate, SubjectOut, SubjectUpdate


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def normalize_subject_code(value: str) -> str:
    code = (value or "").strip().upper()
    if not code:
        raise _bad_request("Subject code cannot be empty.")
    return code


def normalize_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise _bad_request("Subject name cannot be empty.")
    return name


def validate_subject_type(value: str) -> str:
    subject_type = (value or "").strip().upper()
    if subject_type not in SUBJECT_TYPES:
        raise _bad_request(f"Subject type must be one of: {', '.join(SUBJECT_TYPES)}.")
    return subject_type


def validate_load(credits: int, lecture: int, tutorial: int, practical: int) -> None:
    if credits <= 0:
        raise _bad_request("Credits must be greater than zero.")
    if min(lecture, tutorial, practical) < 0:
        raise _bad_request("Lecture, tutorial, and practical hours cannot be negative.")
    if lecture + tutorial + practical == 0:
        raise _bad_request("A subject must have at least one lecture, tutorial, or practical hour.")


def validate_course_semester(db: Session, course_id: int, semester_id: int) -> tuple[Course, Semester]:
    """The semester must exist AND belong to the chosen course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise _not_found("Course not found")

    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise _not_found("Semester not found")

    if semester.course_id != course.id:
        raise _bad_request("Semester does not belong to selected course.")

    return course, semester


def ensure_unique_subject_code(db: Session, subject_code: str, exclude_id: int | None = None) -> None:
    """Subject codes are globally unique across the curriculum."""
    query = db.query(Subject).filter(Subject.subject_code.ilike(subject_code))
    if exclude_id is not None:
        query = query.filter(Subject.id != exclude_id)
    if query.first():
        raise _conflict(f"Subject code '{subject_code}' already exists.")


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize(subject: Subject) -> SubjectOut:
    course = subject.course
    semester = subject.semester
    department = course.department if course else None

    return SubjectOut(
        id=subject.id,
        course_id=subject.course_id,
        semester_id=subject.semester_id,
        subject_code=subject.subject_code,
        name=subject.name,
        description=subject.description,
        credits=subject.credits,
        subject_type=subject.subject_type,
        lecture_hours=subject.lecture_hours,
        tutorial_hours=subject.tutorial_hours,
        practical_hours=subject.practical_hours,
        is_active=subject.is_active,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
        total_hours=subject.lecture_hours + subject.tutorial_hours + subject.practical_hours,
        course_name=course.name if course else None,
        course_code=course.code if course else None,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        academic_year_name=semester.academic_year.name if semester and semester.academic_year else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        department_code=department.code if department else None,
    )


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_subjects(
    db: Session,
    course_id: int | None = None,
    semester_id: int | None = None,
    department_id: int | None = None,
    subject_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[Subject]:
    query = db.query(Subject).join(Course, Subject.course_id == Course.id)

    if course_id is not None:
        query = query.filter(Subject.course_id == course_id)
    if semester_id is not None:
        query = query.filter(Subject.semester_id == semester_id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    if subject_type:
        query = query.filter(Subject.subject_type == subject_type.strip().upper())
    if is_active is not None:
        query = query.filter(Subject.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Subject.subject_code.ilike(term)
            | Subject.name.ilike(term)
            | Subject.description.ilike(term)
        )

    return query.order_by(Subject.subject_code.asc(), Subject.id.asc()).all()


def get_subject_or_404(db: Session, subject_pk: int) -> Subject:
    subject = db.query(Subject).filter(Subject.id == subject_pk).first()
    if not subject:
        raise _not_found("Subject not found")
    return subject


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_subject(db: Session, payload: SubjectCreate) -> Subject:
    subject_code = normalize_subject_code(payload.subject_code)
    name = normalize_name(payload.name)
    subject_type = validate_subject_type(payload.subject_type)

    validate_course_semester(db, payload.course_id, payload.semester_id)
    validate_load(payload.credits, payload.lecture_hours, payload.tutorial_hours, payload.practical_hours)
    ensure_unique_subject_code(db, subject_code)

    subject = Subject(
        course_id=payload.course_id,
        semester_id=payload.semester_id,
        subject_code=subject_code,
        name=name,
        description=(payload.description or "").strip() or None,
        credits=payload.credits,
        subject_type=subject_type,
        lecture_hours=payload.lecture_hours,
        tutorial_hours=payload.tutorial_hours,
        practical_hours=payload.practical_hours,
        is_active=payload.is_active,
    )

    try:
        db.add(subject)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the subject. Please try again.")

    db.refresh(subject)
    return subject


def update_subject(db: Session, subject: Subject, payload: SubjectUpdate) -> Subject:
    subject_code = normalize_subject_code(payload.subject_code)
    name = normalize_name(payload.name)
    subject_type = validate_subject_type(payload.subject_type)

    validate_course_semester(db, payload.course_id, payload.semester_id)
    validate_load(payload.credits, payload.lecture_hours, payload.tutorial_hours, payload.practical_hours)
    ensure_unique_subject_code(db, subject_code, exclude_id=subject.id)

    # Moving a subject to another semester would strand every section it is
    # taught to, which is exactly the mismatch teaching assignments prevent.
    if payload.semester_id != subject.semester_id:
        from app.services import teaching_assignment_service

        if teaching_assignment_service.count_for_subject(db, subject.id):
            raise _bad_request(
                "This subject is assigned to sections in its current semester. "
                "Remove those teaching assignments before moving it."
            )

    try:
        subject.course_id = payload.course_id
        subject.semester_id = payload.semester_id
        subject.subject_code = subject_code
        subject.name = name
        subject.description = (payload.description or "").strip() or None
        subject.credits = payload.credits
        subject.subject_type = subject_type
        subject.lecture_hours = payload.lecture_hours
        subject.tutorial_hours = payload.tutorial_hours
        subject.practical_hours = payload.practical_hours
        subject.is_active = payload.is_active
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the subject. Please try again.")

    db.refresh(subject)
    return subject


def set_status(db: Session, subject: Subject, is_active: bool) -> Subject:
    subject.is_active = is_active
    db.commit()
    db.refresh(subject)
    return subject


def delete_subject(db: Session, subject: Subject) -> None:
    """Hard delete. Prefer deactivating once teaching assignments,
    attendance, or marks reference the subject."""
    from app.services import teaching_assignment_service

    assigned = teaching_assignment_service.count_for_subject(db, subject.id)
    if assigned:
        raise _conflict(
            f"This subject has {assigned} teaching assignment(s). "
            "Remove them before deleting it, or deactivate the subject instead."
        )

    try:
        db.delete(subject)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the subject. Please try again.")
