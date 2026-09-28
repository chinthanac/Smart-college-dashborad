from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_current_admin_user,
    get_current_staff_user,
    get_current_user,
)
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.timetable import (
    SectionCoverage,
    TimetableCopyDay,
    TimetableCopyResult,
    TimetableEntryCreate,
    TimetableEntryOut,
    TimetableEntryStatusUpdate,
    TimetableEntryUpdate,
)
from app.services import timetable_service

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


# --------------------------------------------------------------------------
# static paths first, so "me" / "coverage" are never parsed as {entry_id}
# --------------------------------------------------------------------------

@router.get("/me", response_model=list[TimetableEntryOut])
def list_my_timetable(
    day_of_week: int | None = Query(default=None, ge=0, le=6),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deliberately role-aware rather than faculty-only: a student's timetable
    is their section's, and a faculty-only guard would lock them out."""
    records = timetable_service.list_for_user(
        db, current_user, day_of_week=day_of_week, is_active=is_active
    )
    return [timetable_service.serialize(item) for item in records]


@router.get("/coverage", response_model=SectionCoverage)
def get_section_coverage(
    section_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """How many periods each subject is owed each week versus how many are
    actually placed."""
    return timetable_service.section_coverage(db, section_id)


@router.post("/copy-day", response_model=TimetableCopyResult, status_code=status.HTTP_201_CREATED)
def copy_day(
    payload: TimetableCopyDay,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    created, skipped = timetable_service.copy_day(db, payload)
    return TimetableCopyResult(
        created=[timetable_service.serialize(item) for item in created],
        skipped=skipped,
    )


# --------------------------------------------------------------------------
# collection routes
# --------------------------------------------------------------------------

@router.post("", response_model=TimetableEntryOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TimetableEntryOut, status_code=status.HTTP_201_CREATED)
def create_timetable_entry(
    payload: TimetableEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    entry = timetable_service.create_entry(db, payload)
    return timetable_service.serialize(entry)


@router.get("", response_model=list[TimetableEntryOut])
def list_timetable(
    section_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    teaching_assignment_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    time_slot_id: int | None = Query(default=None),
    day_of_week: int | None = Query(default=None, ge=0, le=6),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    # The scope keys on the SUBJECT's department, matching the teaching
    # assignment list. A faculty member teaching into another department will
    # not see that class here — /me always shows them everything they teach.
    scope = _department_scope_for(db, current_user)
    if scope is not None:
        department_id = scope

    records = timetable_service.list_entries(
        db,
        section_id=section_id,
        faculty_id=faculty_id,
        teaching_assignment_id=teaching_assignment_id,
        subject_id=subject_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        time_slot_id=time_slot_id,
        day_of_week=day_of_week,
        is_active=is_active,
        search=search,
    )
    return [timetable_service.serialize(item) for item in records]


@router.get("/", response_model=list[TimetableEntryOut])
def list_timetable_root(
    section_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    teaching_assignment_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    time_slot_id: int | None = Query(default=None),
    day_of_week: int | None = Query(default=None, ge=0, le=6),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_timetable(
        section_id=section_id,
        faculty_id=faculty_id,
        teaching_assignment_id=teaching_assignment_id,
        subject_id=subject_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        time_slot_id=time_slot_id,
        day_of_week=day_of_week,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# item routes
# --------------------------------------------------------------------------

@router.get("/{entry_id}", response_model=TimetableEntryOut)
def get_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    entry = timetable_service.get_entry_or_404(db, entry_id)

    scope = _department_scope_for(db, current_user)
    assignment = entry.teaching_assignment
    subject = assignment.subject if assignment else None
    if (
        scope is not None
        and subject
        and subject.course
        and subject.course.department_id != scope
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view classes from your own department.",
        )

    return timetable_service.serialize(entry)


@router.put("/{entry_id}", response_model=TimetableEntryOut)
def update_timetable_entry(
    entry_id: int,
    payload: TimetableEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    entry = timetable_service.get_entry_or_404(db, entry_id)
    return timetable_service.serialize(timetable_service.update_entry(db, entry, payload))


@router.patch("/{entry_id}/status", response_model=TimetableEntryOut)
def set_timetable_entry_status(
    entry_id: int,
    payload: TimetableEntryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Suspend a class without losing its place in the grid."""
    entry = timetable_service.get_entry_or_404(db, entry_id)
    return timetable_service.serialize(timetable_service.set_status(db, entry, payload.is_active))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    entry = timetable_service.get_entry_or_404(db, entry_id)
    timetable_service.delete_entry(db, entry)
    return None
