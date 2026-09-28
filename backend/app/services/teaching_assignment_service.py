"""Faculty–Subject–Section teaching assignment service.

Holds the one rule that keeps the timetable honest: a section may only be
taught a subject that belongs to the section's own semester. Cross-department
faculty are deliberately allowed — a Maths lecturer routinely teaches into a
CSE semester — so the department is displayed, never enforced.
"""

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.faculty import Faculty
from app.models.section import Section
from app.models.semester import Semester
from app.models.subject import Subject
from app.models.teaching_assignment import TeachingAssignment
from app.schemas.teaching_assignment import (
    TeachingAssignmentBulkCreate,
    TeachingAssignmentCreate,
    TeachingAssignmentOut,
    TeachingAssignmentSkipped,
    TeachingAssignmentUpdate,
)
from app.services import faculty as faculty_service

DUPLICATE_DETAIL = (
    "This subject is already assigned to this section. "
    "Edit the existing assignment to change the faculty."
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def validate_assignment_chain(
    db: Session,
    faculty_id: int,
    subject_id: int,
    section_id: int,
) -> tuple[Faculty, Subject, Section, Semester]:
    """Resolve Faculty, Subject and Section, then qualify each.

    Every record must exist and be active, and the section must sit in the
    subject's own semester — otherwise "DBMS (CSE Sem 5)" could be handed to
    a Mechanical section. The department is deliberately NOT checked:
    cross-department teaching is legitimate.
    """
    faculty = db.query(Faculty).filter(Faculty.id == faculty_id).first()
    if not faculty:
        raise _not_found("Faculty not found")
    if not faculty.is_active:
        raise _bad_request("Faculty member is inactive and cannot be assigned to teach.")

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise _not_found("Subject not found")
    if not subject.is_active:
        raise _bad_request("Subject is inactive and cannot be assigned.")

    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found")
    if not section.is_active:
        raise _bad_request("Section is inactive and cannot be assigned.")

    if section.semester_id != subject.semester_id:
        raise _bad_request("Section does not belong to the subject's semester.")

    semester = db.query(Semester).filter(Semester.id == subject.semester_id).first()
    if not semester:
        raise _not_found("Semester not found")

    return faculty, subject, section, semester


def ensure_unique_assignment(
    db: Session,
    subject_id: int,
    section_id: int,
    exclude_id: int | None = None,
) -> None:
    """One faculty per subject+section.

    Deliberately does not filter on is_active — the database constraint does
    not either, so an inactive row still occupies the pair. The message routes
    the admin to Edit rather than leaving them stuck.
    """
    query = db.query(TeachingAssignment).filter(
        TeachingAssignment.subject_id == subject_id,
        TeachingAssignment.section_id == section_id,
    )
    if exclude_id is not None:
        query = query.filter(TeachingAssignment.id != exclude_id)
    if query.first():
        raise _conflict(DUPLICATE_DETAIL)


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize(assignment: TeachingAssignment) -> TeachingAssignmentOut:
    faculty = assignment.faculty
    subject = assignment.subject
    section = assignment.section
    semester = assignment.semester
    course = subject.course if subject else None
    department = course.department if course else None
    faculty_department = faculty.department if faculty else None
    academic_year = semester.academic_year if semester else None

    return TeachingAssignmentOut(
        id=assignment.id,
        faculty_id=assignment.faculty_id,
        subject_id=assignment.subject_id,
        section_id=assignment.section_id,
        semester_id=assignment.semester_id,
        notes=assignment.notes,
        is_active=assignment.is_active,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        faculty_name=f"{faculty.first_name} {faculty.last_name}".strip() if faculty else None,
        faculty_code=faculty.faculty_id if faculty else None,
        faculty_designation=faculty.designation if faculty else None,
        faculty_department_id=faculty.department_id if faculty else None,
        faculty_department_name=faculty_department.name if faculty_department else None,
        faculty_department_code=faculty_department.code if faculty_department else None,
        faculty_is_active=faculty.is_active if faculty else None,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        subject_credits=subject.credits if subject else None,
        subject_is_active=subject.is_active if subject else None,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        section_room_number=section.room_number if section else None,
        section_capacity=section.capacity if section else None,
        section_is_active=section.is_active if section else None,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=course.id if course else None,
        course_name=course.name if course else None,
        course_code=course.code if course else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        department_code=department.code if department else None,
        academic_year_id=academic_year.id if academic_year else None,
        academic_year_name=academic_year.name if academic_year else None,
        is_cross_department=bool(faculty and department and faculty.department_id != department.id),
    )


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_teaching_assignments(
    db: Session,
    faculty_id: int | None = None,
    subject_id: int | None = None,
    section_id: int | None = None,
    semester_id: int | None = None,
    course_id: int | None = None,
    department_id: int | None = None,
    faculty_department_id: int | None = None,
    academic_year_id: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[TeachingAssignment]:
    query = (
        db.query(TeachingAssignment)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .join(Section, TeachingAssignment.section_id == Section.id)
        .join(Faculty, TeachingAssignment.faculty_id == Faculty.id)
        .join(Course, Subject.course_id == Course.id)
        .join(Semester, TeachingAssignment.semester_id == Semester.id)
    )

    if faculty_id is not None:
        query = query.filter(TeachingAssignment.faculty_id == faculty_id)
    if subject_id is not None:
        query = query.filter(TeachingAssignment.subject_id == subject_id)
    if section_id is not None:
        query = query.filter(TeachingAssignment.section_id == section_id)
    if semester_id is not None:
        query = query.filter(TeachingAssignment.semester_id == semester_id)
    if course_id is not None:
        query = query.filter(Subject.course_id == course_id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    if faculty_department_id is not None:
        query = query.filter(Faculty.department_id == faculty_department_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if is_active is not None:
        query = query.filter(TeachingAssignment.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Subject.subject_code.ilike(term)
            | Subject.name.ilike(term)
            | Faculty.first_name.ilike(term)
            | Faculty.last_name.ilike(term)
            | Faculty.faculty_id.ilike(term)
            | Section.name.ilike(term)
            | Section.code.ilike(term)
        )

    return query.order_by(
        Subject.subject_code.asc(), Section.name.asc(), TeachingAssignment.id.asc()
    ).all()


def get_teaching_assignment_or_404(db: Session, assignment_pk: int) -> TeachingAssignment:
    assignment = db.query(TeachingAssignment).filter(TeachingAssignment.id == assignment_pk).first()
    if not assignment:
        raise _not_found("Teaching assignment not found")
    return assignment


def list_for_faculty_user(
    db: Session,
    user_id: int,
    semester_id: int | None = None,
    academic_year_id: int | None = None,
) -> list[TeachingAssignment]:
    """Everything the signed-in faculty member teaches, including any
    cross-department assignments the department-scoped list would hide."""
    faculty = faculty_service.get_faculty_for_user(db, user_id)
    return list_teaching_assignments(
        db,
        faculty_id=faculty.id,
        semester_id=semester_id,
        academic_year_id=academic_year_id,
    )


def count_for_subject(db: Session, subject_id: int) -> int:
    return db.query(TeachingAssignment).filter(TeachingAssignment.subject_id == subject_id).count()


def count_for_section(db: Session, section_id: int) -> int:
    return db.query(TeachingAssignment).filter(TeachingAssignment.section_id == section_id).count()


def count_for_faculty(db: Session, faculty_id: int) -> int:
    return db.query(TeachingAssignment).filter(TeachingAssignment.faculty_id == faculty_id).count()


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_teaching_assignment(db: Session, payload: TeachingAssignmentCreate) -> TeachingAssignment:
    notes = (payload.notes or "").strip() or None

    _, subject, _, _ = validate_assignment_chain(
        db, payload.faculty_id, payload.subject_id, payload.section_id
    )
    ensure_unique_assignment(db, payload.subject_id, payload.section_id)

    assignment = TeachingAssignment(
        faculty_id=payload.faculty_id,
        subject_id=payload.subject_id,
        section_id=payload.section_id,
        semester_id=subject.semester_id,
        notes=notes,
        is_active=payload.is_active,
    )

    try:
        db.add(assignment)
        db.commit()
    except IntegrityError:
        # The unique constraint can still fire if another admin wrote the same
        # pair between our check above and this commit. Report the real reason
        # rather than a "try again" that would never succeed.
        db.rollback()
        raise _conflict(DUPLICATE_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the teaching assignment. Please try again.")

    db.refresh(assignment)
    return assignment


def update_teaching_assignment(
    db: Session,
    assignment: TeachingAssignment,
    payload: TeachingAssignmentUpdate,
) -> TeachingAssignment:
    notes = (payload.notes or "").strip() or None

    _, subject, _, _ = validate_assignment_chain(
        db, payload.faculty_id, payload.subject_id, payload.section_id
    )
    ensure_unique_assignment(db, payload.subject_id, payload.section_id, exclude_id=assignment.id)

    try:
        assignment.faculty_id = payload.faculty_id
        assignment.subject_id = payload.subject_id
        assignment.section_id = payload.section_id
        assignment.semester_id = subject.semester_id
        assignment.notes = notes
        assignment.is_active = payload.is_active
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(DUPLICATE_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the teaching assignment. Please try again.")

    db.refresh(assignment)
    return assignment


def set_status(db: Session, assignment: TeachingAssignment, is_active: bool) -> TeachingAssignment:
    assignment.is_active = is_active
    db.commit()
    db.refresh(assignment)
    return assignment


def bulk_assign(
    db: Session,
    payload: TeachingAssignmentBulkCreate,
) -> tuple[list[TeachingAssignment], list[TeachingAssignmentSkipped]]:
    """Assign one faculty member to one subject across several sections.

    A missing record or a semester mismatch aborts the whole batch — the admin
    fixes the input and retries. Sections that already have this subject are
    skipped and reported instead, because partial overlap is the normal case
    ("Prof X now also takes sections C and D").
    """
    notes = (payload.notes or "").strip() or None
    section_ids = list(dict.fromkeys(payload.section_ids))

    created: list[TeachingAssignment] = []
    skipped: list[TeachingAssignmentSkipped] = []
    pending: list[TeachingAssignment] = []

    # Validate every section before writing anything.
    for section_id in section_ids:
        _, subject, section, _ = validate_assignment_chain(
            db, payload.faculty_id, payload.subject_id, section_id
        )

        existing = (
            db.query(TeachingAssignment)
            .filter(
                TeachingAssignment.subject_id == payload.subject_id,
                TeachingAssignment.section_id == section_id,
            )
            .first()
        )
        if existing:
            holder = existing.faculty
            holder_name = f"{holder.first_name} {holder.last_name}".strip() if holder else "another faculty member"
            skipped.append(
                TeachingAssignmentSkipped(
                    section_id=section_id,
                    section_name=section.name,
                    reason=f"Already assigned to {holder_name}.",
                )
            )
            continue

        pending.append(
            TeachingAssignment(
                faculty_id=payload.faculty_id,
                subject_id=payload.subject_id,
                section_id=section_id,
                semester_id=subject.semester_id,
                notes=notes,
                is_active=payload.is_active,
            )
        )

    if not pending:
        return created, skipped

    try:
        for assignment in pending:
            db.add(assignment)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(DUPLICATE_DETAIL)
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the teaching assignments. Please try again.")

    for assignment in pending:
        db.refresh(assignment)
        created.append(assignment)

    return created, skipped


def delete_teaching_assignment(db: Session, assignment: TeachingAssignment) -> None:
    """Hard delete. Prefer deactivating once attendance and marks reference
    this assignment, so the teaching history survives."""
    try:
        db.delete(assignment)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the teaching assignment. Please try again.")
