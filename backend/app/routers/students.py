from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_current_admin_user,
    get_current_staff_user,
    get_current_student_user,
)
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.student import (
    GENDERS,
    STATUSES,
    StudentCreate,
    StudentCreated,
    StudentIdSuggestion,
    StudentOptions,
    StudentOut,
    StudentPasswordReset,
    StudentProfileUpdate,
    StudentStatusUpdate,
    StudentUpdate,
)
from app.services import attendance_service, marks_service, student_service

router = APIRouter()


def _department_scope_for(db: Session, current_user: User) -> int | None:
    """Admins see every student; Faculty see only their own department."""
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
# static paths first, so they are never parsed as {student_id}
# --------------------------------------------------------------------------

@router.get("/options", response_model=StudentOptions)
def get_student_options():
    return StudentOptions(genders=GENDERS, statuses=STATUSES)


@router.get("/suggest-id", response_model=StudentIdSuggestion)
def get_suggested_student_id(
    department_id: int = Query(..., gt=0),
    academic_year_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """A starting point only — the Admin can overwrite it freely."""
    return StudentIdSuggestion(
        suggested_student_id=student_service.suggest_student_id(db, department_id, academic_year_id)
    )


@router.get("/me/profile", response_model=StudentOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student_user),
):
    student = student_service.get_student_for_user(db, current_user.id)
    return student_service.serialize(student)


@router.put("/me/profile", response_model=StudentOut)
def update_my_profile(
    payload: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_student_user),
):
    student = student_service.get_student_for_user(db, current_user.id)
    updated = student_service.update_own_profile(db, student, payload)
    return student_service.serialize(updated)


# --------------------------------------------------------------------------
# collection routes
# --------------------------------------------------------------------------

@router.post("", response_model=StudentCreated, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=StudentCreated, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student, generated_password = student_service.create_student(db, payload)
    return StudentCreated(
        **student_service.serialize(student).model_dump(),
        generated_password=generated_password,
    )


@router.get("", response_model=list[StudentOut])
def list_students(
    department_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    student_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    scope = _department_scope_for(db, current_user)
    if scope is not None:
        # a Faculty request can only ever see their own department
        department_id = scope

    records = student_service.list_students(
        db,
        department_id=department_id,
        course_id=course_id,
        academic_year_id=academic_year_id,
        semester_id=semester_id,
        section_id=section_id,
        student_status=student_status,
        search=search,
    )
    return [student_service.serialize(item) for item in records]


@router.get("/", response_model=list[StudentOut])
def list_students_root(
    department_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    student_status: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_students(
        department_id=department_id,
        course_id=course_id,
        academic_year_id=academic_year_id,
        semester_id=semester_id,
        section_id=section_id,
        student_status=student_status,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# item routes
# --------------------------------------------------------------------------

@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    student = student_service.get_student_or_404(db, student_id)

    scope = _department_scope_for(db, current_user)
    if scope is not None and student.department_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view students from your own department.",
        )

    return student_service.serialize(student)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student = student_service.get_student_or_404(db, student_id)
    updated = student_service.update_student(db, student, payload)
    return student_service.serialize(updated)


@router.patch("/{student_id}/activate", response_model=StudentOut)
def activate_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student = student_service.get_student_or_404(db, student_id)
    return student_service.serialize(student_service.set_status(db, student, "ACTIVE"))


@router.patch("/{student_id}/deactivate", response_model=StudentOut)
def deactivate_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student = student_service.get_student_or_404(db, student_id)
    return student_service.serialize(student_service.set_status(db, student, "INACTIVE"))


@router.patch("/{student_id}/status", response_model=StudentOut)
def set_student_status(
    student_id: int,
    payload: StudentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Covers GRADUATED and SUSPENDED alongside ACTIVE/INACTIVE."""
    student = student_service.get_student_or_404(db, student_id)
    return student_service.serialize(student_service.set_status(db, student, payload.status))


@router.post("/{student_id}/reset-password", response_model=StudentCreated)
def reset_student_password(
    student_id: int,
    payload: StudentPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student = student_service.get_student_or_404(db, student_id)
    generated_password = student_service.reset_password(db, student, payload.password)
    return StudentCreated(
        **student_service.serialize(student).model_dump(),
        generated_password=generated_password,
    )


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    student = student_service.get_student_or_404(db, student_id)

    marked = attendance_service.count_for_student(db, student.id)
    if marked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This student has {marked} attendance record(s). Set their status to "
                "INACTIVE or GRADUATED instead — deleting them would strand that history."
            ),
        )

    graded = marks_service.count_for_student(db, student.id)
    if graded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This student has {graded} mark record(s). Set their status to "
                "INACTIVE or GRADUATED instead — deleting them would strand that history."
            ),
        )

    student_service.delete_student(db, student)
    return None
