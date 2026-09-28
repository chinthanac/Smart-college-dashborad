from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_current_admin_user,
    get_current_faculty_user,
    get_current_staff_user,
)
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.teaching_assignment import (
    TeachingAssignmentBulkCreate,
    TeachingAssignmentBulkResult,
    TeachingAssignmentCreate,
    TeachingAssignmentOut,
    TeachingAssignmentStatusUpdate,
    TeachingAssignmentUpdate,
)
from app.services import assessment_service, attendance_service, teaching_assignment_service

router = APIRouter()


def _department_scope_for(db: Session, current_user: User) -> int | None:
    """Admins see every assignment; Faculty see their own department's."""
    if current_user.role == "ADMIN":
        return None

    faculty = db.query(Faculty).filter(Faculty.user_id == current_user.id).first()
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No faculty profile is linked to this account.",
        )
    return faculty.department_id


# --------------------------------------------------------------------------
# static paths first, so "me" / "bulk" are never parsed as {assignment_id}
# --------------------------------------------------------------------------

@router.get("/me", response_model=list[TeachingAssignmentOut])
def list_my_assignments(
    semester_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    records = teaching_assignment_service.list_for_faculty_user(
        db, current_user.id, semester_id=semester_id, academic_year_id=academic_year_id
    )
    return [teaching_assignment_service.serialize(item) for item in records]


@router.post("/bulk", response_model=TeachingAssignmentBulkResult, status_code=status.HTTP_201_CREATED)
def bulk_assign(
    payload: TeachingAssignmentBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    created, skipped = teaching_assignment_service.bulk_assign(db, payload)
    return TeachingAssignmentBulkResult(
        created=[teaching_assignment_service.serialize(item) for item in created],
        skipped=skipped,
    )


# --------------------------------------------------------------------------
# collection routes
# --------------------------------------------------------------------------

@router.post("", response_model=TeachingAssignmentOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TeachingAssignmentOut, status_code=status.HTTP_201_CREATED)
def create_teaching_assignment(
    payload: TeachingAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    assignment = teaching_assignment_service.create_teaching_assignment(db, payload)
    return teaching_assignment_service.serialize(assignment)


@router.get("", response_model=list[TeachingAssignmentOut])
def list_teaching_assignments(
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    faculty_department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    # The scope keys on the SUBJECT's department. A faculty member teaching
    # cross-department will not see that row here — /me always shows them
    # everything they teach.
    scope = _department_scope_for(db, current_user)
    if scope is not None:
        department_id = scope

    records = teaching_assignment_service.list_teaching_assignments(
        db,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        faculty_department_id=faculty_department_id,
        academic_year_id=academic_year_id,
        is_active=is_active,
        search=search,
    )
    return [teaching_assignment_service.serialize(item) for item in records]


@router.get("/", response_model=list[TeachingAssignmentOut])
def list_teaching_assignments_root(
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    faculty_department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_teaching_assignments(
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        faculty_department_id=faculty_department_id,
        academic_year_id=academic_year_id,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# item routes
# --------------------------------------------------------------------------

@router.get("/{assignment_id}", response_model=TeachingAssignmentOut)
def get_teaching_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    assignment = teaching_assignment_service.get_teaching_assignment_or_404(db, assignment_id)

    scope = _department_scope_for(db, current_user)
    if (
        scope is not None
        and assignment.subject
        and assignment.subject.course
        and assignment.subject.course.department_id != scope
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view teaching assignments from your own department.",
        )

    return teaching_assignment_service.serialize(assignment)


@router.put("/{assignment_id}", response_model=TeachingAssignmentOut)
def update_teaching_assignment(
    assignment_id: int,
    payload: TeachingAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    assignment = teaching_assignment_service.get_teaching_assignment_or_404(db, assignment_id)
    updated = teaching_assignment_service.update_teaching_assignment(db, assignment, payload)
    return teaching_assignment_service.serialize(updated)


@router.patch("/{assignment_id}/status", response_model=TeachingAssignmentOut)
def set_teaching_assignment_status(
    assignment_id: int,
    payload: TeachingAssignmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Pause an assignment (faculty on leave) without losing the record."""
    assignment = teaching_assignment_service.get_teaching_assignment_or_404(db, assignment_id)
    updated = teaching_assignment_service.set_status(db, assignment, payload.is_active)
    return teaching_assignment_service.serialize(updated)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_teaching_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    assignment = teaching_assignment_service.get_teaching_assignment_or_404(db, assignment_id)

    marked = attendance_service.count_for_assignment(db, assignment.id)
    if marked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This assignment has {marked} attendance session(s) on record. "
                "Deactivate it instead, so the register survives."
            ),
        )

    assessed = assessment_service.count_for_assignment(db, assignment.id)
    if assessed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This assignment has {assessed} assessment(s) on record. "
                "Deactivate it instead, so the marks survive."
            ),
        )

    teaching_assignment_service.delete_teaching_assignment(db, assignment)
    return None
