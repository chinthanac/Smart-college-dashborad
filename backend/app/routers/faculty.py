from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user, get_current_faculty_user
from app.models.user import User
from app.schemas.faculty import (
    DESIGNATIONS,
    EMPLOYEE_TYPES,
    FacultyCreate,
    FacultyCreated,
    FacultyOptions,
    FacultyOut,
    FacultyPasswordReset,
    FacultyProfileUpdate,
    FacultyStatusUpdate,
    FacultyUpdate,
)
from app.services import faculty as faculty_service

router = APIRouter()


# --------------------------------------------------------------------------
# static paths first, so "options" / "me" are never parsed as {faculty_id}
# --------------------------------------------------------------------------

@router.get("/options", response_model=FacultyOptions)
def get_faculty_options():
    """The controlled lists the Add/Edit form must offer."""
    return FacultyOptions(designations=DESIGNATIONS, employee_types=EMPLOYEE_TYPES)


@router.get("/me/profile", response_model=FacultyOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    faculty = faculty_service.get_faculty_for_user(db, current_user.id)
    return faculty_service.serialize(faculty)


@router.put("/me/profile", response_model=FacultyOut)
def update_my_profile(
    payload: FacultyProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    faculty = faculty_service.get_faculty_for_user(db, current_user.id)
    updated = faculty_service.update_own_profile(db, faculty, payload)
    return faculty_service.serialize(updated)


# --------------------------------------------------------------------------
# admin-only collection routes
# --------------------------------------------------------------------------

@router.post("", response_model=FacultyCreated, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FacultyCreated, status_code=status.HTTP_201_CREATED)
def create_faculty(
    payload: FacultyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    faculty, generated_password = faculty_service.create_faculty(db, payload)
    return FacultyCreated(
        **faculty_service.serialize(faculty).model_dump(),
        generated_password=generated_password,
    )


@router.get("", response_model=list[FacultyOut])
def list_faculty(
    department_id: int | None = Query(default=None),
    designation: str | None = Query(default=None),
    employee_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    records = faculty_service.list_faculty(
        db,
        department_id=department_id,
        designation=designation,
        employee_type=employee_type,
        is_active=is_active,
        search=search,
    )
    return [faculty_service.serialize(item) for item in records]


@router.get("/", response_model=list[FacultyOut])
def list_faculty_root(
    department_id: int | None = Query(default=None),
    designation: str | None = Query(default=None),
    employee_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_faculty(
        department_id=department_id,
        designation=designation,
        employee_type=employee_type,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# admin-only item routes
# --------------------------------------------------------------------------

@router.get("/{faculty_id}", response_model=FacultyOut)
def get_faculty(
    faculty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    faculty = faculty_service.get_faculty_or_404(db, faculty_id)
    return faculty_service.serialize(faculty)


@router.put("/{faculty_id}", response_model=FacultyOut)
def update_faculty(
    faculty_id: int,
    payload: FacultyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    faculty = faculty_service.get_faculty_or_404(db, faculty_id)
    updated = faculty_service.update_faculty(db, faculty, payload)
    return faculty_service.serialize(updated)


@router.patch("/{faculty_id}/status", response_model=FacultyOut)
def set_faculty_status(
    faculty_id: int,
    payload: FacultyStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Activate or deactivate. The record is kept so history stays intact."""
    faculty = faculty_service.get_faculty_or_404(db, faculty_id)
    updated = faculty_service.set_status(db, faculty, payload.is_active)
    return faculty_service.serialize(updated)


@router.post("/{faculty_id}/reset-password", response_model=FacultyCreated)
def reset_faculty_password(
    faculty_id: int,
    payload: FacultyPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    faculty = faculty_service.get_faculty_or_404(db, faculty_id)
    generated_password = faculty_service.reset_password(db, faculty, payload.password)
    return FacultyCreated(
        **faculty_service.serialize(faculty).model_dump(),
        generated_password=generated_password,
    )


@router.delete("/{faculty_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faculty(
    faculty_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    faculty = faculty_service.get_faculty_or_404(db, faculty_id)
    faculty_service.delete_faculty(db, faculty)
    return None
