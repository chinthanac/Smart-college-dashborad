from datetime import date

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
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentOptions,
    AssessmentOut,
    AssessmentStatusUpdate,
    AssessmentUpdate,
    WeightageBudget,
)
from app.services import assessment_service

router = APIRouter()


def _department_scope_for(db: Session, current_user: User) -> int | None:
    """Admins see the whole college; Faculty see their own department."""
    if current_user.role == "ADMIN":
        return None

    faculty = db.query(Faculty).filter(Faculty.user_id == current_user.id).first()
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No faculty profile is linked to this account.",
        )
    return faculty.department_id


def _ensure_in_scope(db: Session, current_user: User, assessment) -> None:
    scope = _department_scope_for(db, current_user)
    if scope is None:
        return
    subject = assessment.subject
    course = subject.course if subject else None
    if course and course.department_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view assessments from your own department.",
        )


# --------------------------------------------------------------------------
# static paths first, so "options" / "me" / "budget" are never parsed as
# {assessment_id}
# --------------------------------------------------------------------------

@router.get("/options", response_model=AssessmentOptions)
def get_assessment_options():
    return assessment_service.options()


@router.get("/me", response_model=list[AssessmentOut])
def list_my_assessments(
    semester_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    """Every assessment on a class the signed-in lecturer teaches.

    The faculty id comes from the token, never a query parameter, so this
    cannot be pointed at somebody else's classes. It also shows
    cross-department teaching, which the department-scoped list would hide.
    """
    faculty = assessment_service.faculty_for_user(db, current_user)
    records = assessment_service.list_assessments(
        db,
        faculty_id=faculty.id,
        semester_id=semester_id,
        section_id=section_id,
        subject_id=subject_id,
        status=status_filter,
    )
    return assessment_service.serialize_many(db, records, current_user=current_user)


@router.get("/budget", response_model=WeightageBudget)
def get_weightage_budget(
    teaching_assignment_id: int = Query(..., gt=0),
    exclude_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """What is left of a class's 100%, and what has taken the rest.

    The form reads this before it submits, so the constraint is visible while
    the number is being typed rather than explained by an error afterwards.
    """
    assignment = assessment_service.get_assignment_or_404(db, teaching_assignment_id)
    assessment_service.ensure_can_manage_assignment(db, current_user, assignment)
    return assessment_service.weightage_budget(db, assignment, exclude_id=exclude_id)


# --------------------------------------------------------------------------
# collection routes
# --------------------------------------------------------------------------

@router.post("", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
def create_assessment(
    payload: AssessmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Admin, or the faculty member who teaches the class."""
    assessment = assessment_service.create_assessment(db, current_user, payload)
    return assessment_service.serialize_one(db, assessment, current_user=current_user)


@router.get("", response_model=list[AssessmentOut])
def list_assessments(
    teaching_assignment_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    assessment_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
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

    records = assessment_service.list_assessments(
        db,
        teaching_assignment_id=teaching_assignment_id,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        assessment_type=assessment_type,
        status=status_filter,
        is_active=is_active,
        search=search,
    )
    return assessment_service.serialize_many(db, records, current_user=current_user)


@router.get("/", response_model=list[AssessmentOut])
def list_assessments_root(
    teaching_assignment_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    assessment_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_assessments(
        teaching_assignment_id=teaching_assignment_id,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        assessment_type=assessment_type,
        status_filter=status_filter,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# item routes
# --------------------------------------------------------------------------

@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    assessment = assessment_service.get_assessment_or_404(db, assessment_id)
    _ensure_in_scope(db, current_user, assessment)
    return assessment_service.serialize_one(db, assessment, current_user=current_user)


@router.patch("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(
    assessment_id: int,
    payload: AssessmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """PATCH, not PUT: the form edits one field at a time, and a PUT would
    make an omitted field mean "clear it"."""
    assessment = assessment_service.get_assessment_or_404(db, assessment_id)
    updated = assessment_service.update_assessment(db, current_user, assessment, payload)
    return assessment_service.serialize_one(db, updated, current_user=current_user)


@router.patch("/{assessment_id}/status", response_model=AssessmentOut)
def set_assessment_status(
    assessment_id: int,
    payload: AssessmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """publish / lock / unlock. Unlock is admin-only."""
    assessment = assessment_service.get_assessment_or_404(db, assessment_id)
    updated = assessment_service.set_status(db, current_user, assessment, payload)
    return assessment_service.serialize_one(db, updated, current_user=current_user)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assessment(
    assessment_id: int,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Admin only, and refused while marks exist unless ?force=true."""
    assessment = assessment_service.get_assessment_or_404(db, assessment_id)
    assessment_service.delete_assessment(db, current_user, assessment, force=force)
    return None
