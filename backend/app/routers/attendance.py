from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    get_current_admin_user,
    get_current_faculty_user,
    get_current_staff_user,
    get_current_user,
)
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.attendance import (
    DEFAULT_ATTENDANCE_THRESHOLD,
    AttendanceOptions,
    AttendanceSessionOut,
    AttendanceSessionStatusUpdate,
    AttendanceSheet,
    AttendanceSheetSave,
    MarkableClassOut,
    SectionAttendanceReport,
    StudentAttendanceSummary,
)
from app.services import attendance_service

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
# static paths first, so "options" / "me" / "sheet" / "sessions" / "report"
# are never parsed as {session_id}
# --------------------------------------------------------------------------

@router.get("/options", response_model=AttendanceOptions)
def get_attendance_options():
    return attendance_service.options()


@router.get("/me", response_model=StudentAttendanceSummary)
def get_my_attendance(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    threshold: float = Query(default=DEFAULT_ATTENDANCE_THRESHOLD, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A student's own record. Staff get a 400 pointing at the reports."""
    return attendance_service.summary_for_user(
        db, current_user, from_date=from_date, to_date=to_date, threshold=threshold
    )


@router.get("/my-classes", response_model=list[MarkableClassOut])
def list_my_classes(
    class_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    """What the signed-in lecturer has to mark on a given day.

    The faculty id comes from the token, never a query parameter, so this
    cannot be pointed at somebody else's timetable.
    """
    return attendance_service.list_markable_classes(
        db, current_user, class_date or date.today()
    )


@router.get("/sheet", response_model=AttendanceSheet)
def get_attendance_sheet(
    timetable_entry_id: int = Query(..., gt=0),
    class_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Read-only. Opening a sheet never creates a session."""
    return attendance_service.build_sheet(db, current_user, timetable_entry_id, class_date)


@router.post("/sheet", response_model=AttendanceSheet)
def save_attendance_sheet(
    payload: AttendanceSheetSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Create or correct one register.

    200 rather than 201: saving the same sheet again corrects it in place, so
    the call is idempotent from the caller's point of view.
    """
    session = attendance_service.save_sheet(db, current_user, payload)
    return attendance_service.build_sheet(
        db, current_user, session.timetable_entry_id, session.class_date
    )


@router.get("/report/section", response_model=SectionAttendanceReport)
def get_section_report(
    section_id: int = Query(..., gt=0),
    subject_id: int | None = Query(default=None),
    teaching_assignment_id: int | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    threshold: float = Query(default=DEFAULT_ATTENDANCE_THRESHOLD, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return attendance_service.section_report(
        db,
        section_id=section_id,
        subject_id=subject_id,
        teaching_assignment_id=teaching_assignment_id,
        from_date=from_date,
        to_date=to_date,
        threshold=threshold,
    )


@router.get("/report/student", response_model=StudentAttendanceSummary)
def get_student_report(
    student_id: int = Query(..., gt=0),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    threshold: float = Query(default=DEFAULT_ATTENDANCE_THRESHOLD, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    from app.services import student_service

    student = student_service.get_student_or_404(db, student_id)
    return attendance_service.student_summary(
        db, student, from_date=from_date, to_date=to_date, threshold=threshold
    )


# --------------------------------------------------------------------------
# collection routes
# --------------------------------------------------------------------------

@router.get("/sessions", response_model=list[AttendanceSessionOut])
def list_sessions(
    timetable_entry_id: int | None = Query(default=None),
    teaching_assignment_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    class_date: date | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    session_status: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    # Scoped on the SUBJECT's department, matching the timetable list.
    scope = _department_scope_for(db, current_user)
    if scope is not None:
        department_id = scope

    records = attendance_service.list_sessions(
        db,
        timetable_entry_id=timetable_entry_id,
        teaching_assignment_id=teaching_assignment_id,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        student_id=student_id,
        class_date=class_date,
        from_date=from_date,
        to_date=to_date,
        session_status=session_status,
        is_active=is_active,
        search=search,
    )
    return [attendance_service.serialize_session(item) for item in records]


@router.get("", response_model=list[AttendanceSessionOut])
def list_sessions_root(
    timetable_entry_id: int | None = Query(default=None),
    teaching_assignment_id: int | None = Query(default=None),
    faculty_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    department_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    student_id: int | None = Query(default=None),
    class_date: date | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    session_status: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    return list_sessions(
        timetable_entry_id=timetable_entry_id,
        teaching_assignment_id=teaching_assignment_id,
        faculty_id=faculty_id,
        subject_id=subject_id,
        section_id=section_id,
        semester_id=semester_id,
        course_id=course_id,
        department_id=department_id,
        academic_year_id=academic_year_id,
        student_id=student_id,
        class_date=class_date,
        from_date=from_date,
        to_date=to_date,
        session_status=session_status,
        is_active=is_active,
        search=search,
        db=db,
        current_user=current_user,
    )


# --------------------------------------------------------------------------
# item routes
# --------------------------------------------------------------------------

@router.get("/sessions/{session_id}", response_model=AttendanceSheet)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    session = attendance_service.get_session_or_404(db, session_id)
    return attendance_service.build_sheet(
        db, current_user, session.timetable_entry_id, session.class_date
    )


@router.patch("/sessions/{session_id}/status", response_model=AttendanceSessionOut)
def set_session_status(
    session_id: int,
    payload: AttendanceSessionStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Cancel a class after the fact, or reopen one cancelled by mistake."""
    session = attendance_service.get_session_or_404(db, session_id)
    return attendance_service.serialize_session(
        attendance_service.set_session_status(db, session, payload)
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    session = attendance_service.get_session_or_404(db, session_id)
    attendance_service.delete_session(db, session)
    return None
