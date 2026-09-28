from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user, get_current_staff_user
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.subject import (
    SUBJECT_TYPES,
    SubjectCreate,
    SubjectOptions,
    SubjectOut,
    SubjectStatusUpdate,
    SubjectUpdate,
)
from app.services import subject_service

router = APIRouter()


def _department_scope_for(db: Session, current_user: User) -> int | None:
    """Admins see the whole curriculum; Faculty see their department's."""
    if current_user.role == "ADMIN":
        return None

    faculty = db.query(Faculty).filter(Faculty.user_id == current_user.id).first()
    if not faculty:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No faculty profile is linked to this account.",
        )
    return faculty.department_id


@router.get("/options", response_model=SubjectOptions)
def get_subject_options():
    return SubjectOptions(subject_types=SUBJECT_TYPES)


@router.post("", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    subject = subject_service.create_subject(db, payload)
    return subject_service.serialize(subject)


@router.get("", response_model=list[SubjectOut])
def list_subjects(
    course_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    scope = _department_scope_for(db, current_user)
    if scope is not None:
        department_id = scope

    records = subject_service.list_subjects(
        db,
        course_id=course_id,
        semester_id=semester_id,
        department_id=department_id,
        subject_type=subject_type,
        is_active=is_active,
        search=search,
    )
    return [subject_service.serialize(item) for item in records]


@router.get("/", response_model=list[SubjectOut])
def list_subjects_root(
    course_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    subject_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_subjects(
        course_id=course_id,
        semester_id=semester_id,
        department_id=department_id,
        subject_type=subject_type,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    subject = subject_service.get_subject_or_404(db, subject_id)

    scope = _department_scope_for(db, current_user)
    if scope is not None and subject.course and subject.course.department_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view subjects from your own department.",
        )

    return subject_service.serialize(subject)


@router.put("/{subject_id}", response_model=SubjectOut)
def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    subject = subject_service.get_subject_or_404(db, subject_id)
    return subject_service.serialize(subject_service.update_subject(db, subject, payload))


@router.patch("/{subject_id}/status", response_model=SubjectOut)
def set_subject_status(
    subject_id: int,
    payload: SubjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Activate or deactivate. Deactivating keeps the subject and any
    history that will later reference it."""
    subject = subject_service.get_subject_or_404(db, subject_id)
    return subject_service.serialize(subject_service.set_status(db, subject, payload.is_active))


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    subject = subject_service.get_subject_or_404(db, subject_id)
    subject_service.delete_subject(db, subject)
    return None
