"""Attendance.

A session is one scheduled class on one real date; a record is one student's
standing within it. What this module owns:

  * that a session's date really is a day that class meets — a register dated
    on a Thursday for a Monday class inflates the denominator of every
    percentage it touches, silently and permanently;
  * that the roster a sheet is built from is the section's own ACTIVE students,
    while nothing that reads a saved register ever filters on status — a
    student suspended in November must keep October's attendance;
  * that saving twice corrects the register rather than duplicating it;
  * that a percentage counts HELD sessions only.

Who teaches what to whom is settled by the teaching assignment, and when the
class meets is settled by the timetable. Neither can be contradicted here: a
session copies its whole identity from the entry it points at and accepts none
of it from the client.
"""

from datetime import date, timedelta

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.course import Course
from app.models.faculty import Faculty
from app.models.section import Section
from app.models.semester import Semester
from app.models.student import Student
from app.models.subject import Subject
from app.models.teaching_assignment import TeachingAssignment
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.user import User
from app.schemas.attendance import (
    ATTENDANCE_BACKDATE_DAYS,
    ATTENDANCE_STATUSES,
    DEFAULT_ATTENDANCE_THRESHOLD,
    DEFAULT_RECORD_STATUS,
    DEFAULT_SESSION_STATUS,
    EXCUSED_STATUSES,
    PRESENT_STATUSES,
    SESSION_STATUSES,
    AttendanceOptions,
    AttendanceRecordOut,
    AttendanceSessionOut,
    AttendanceSessionStatusUpdate,
    AttendanceSheet,
    AttendanceSheetSave,
    MarkableClassOut,
    SectionAttendanceReport,
    SectionAttendanceRow,
    StudentAttendanceSummary,
    SubjectAttendanceSummary,
)
from app.schemas.timetable import DAY_NAMES


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=detail)


def _is_cancelled(session: AttendanceSession) -> bool:
    return (session.session_status or "").upper() == "CANCELLED"


def _day_name(day_of_week: int | None) -> str | None:
    if day_of_week is None or not 0 <= day_of_week < len(DAY_NAMES):
        return None
    return DAY_NAMES[day_of_week]


def _student_name(student: Student | None) -> str | None:
    if not student:
        return None
    return f"{student.first_name} {student.last_name}".strip()


def _faculty_name(faculty: Faculty | None) -> str | None:
    if not faculty:
        return None
    return f"{faculty.first_name} {faculty.last_name}".strip()


def options() -> AttendanceOptions:
    return AttendanceOptions(
        statuses=ATTENDANCE_STATUSES,
        session_statuses=SESSION_STATUSES,
        present_statuses=PRESENT_STATUSES,
        excused_statuses=EXCUSED_STATUSES,
        default_status=DEFAULT_RECORD_STATUS,
        backdate_days=ATTENDANCE_BACKDATE_DAYS,
        default_threshold=DEFAULT_ATTENDANCE_THRESHOLD,
    )


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def validate_record_status(value: str | None) -> str:
    status = (value or DEFAULT_RECORD_STATUS).strip().upper()
    if status not in ATTENDANCE_STATUSES:
        raise _bad_request(f"Status must be one of: {', '.join(ATTENDANCE_STATUSES)}.")
    return status


def validate_session_status(value: str | None) -> str:
    status = (value or DEFAULT_SESSION_STATUS).strip().upper()
    if status not in SESSION_STATUSES:
        raise _bad_request(f"Session status must be one of: {', '.join(SESSION_STATUSES)}.")
    return status


def resolve_entry(
    db: Session, timetable_entry_id: int, *, for_new_session: bool
) -> TimetableEntry:
    """The scheduled class a register belongs to.

    A paused class refuses a NEW sheet but keeps its existing ones editable: a
    pause is usually applied after a month of real teaching, and locking those
    registers would make an honest mistake uncorrectable.
    """
    entry = (
        db.query(TimetableEntry).filter(TimetableEntry.id == timetable_entry_id).first()
    )
    if not entry:
        raise _not_found("Scheduled class not found.")

    assignment = entry.teaching_assignment
    if not assignment:
        raise _bad_request("This class is no longer linked to a teaching assignment.")
    if not assignment.subject:
        raise _bad_request("This class is no longer linked to a subject.")

    if for_new_session and not entry.is_active:
        raise _bad_request(
            "This class is paused and cannot be marked. Ask your admin to reactivate it."
        )

    return entry


def validate_class_date(
    db: Session, entry: TimetableEntry, class_date: date, *, is_admin: bool
) -> date:
    today = date.today()
    assignment = entry.teaching_assignment
    subject = assignment.subject if assignment else None
    subject_name = subject.name if subject else "This class"

    if class_date > today:
        raise _bad_request(
            "You cannot mark attendance for a class that has not happened yet."
        )

    if class_date.weekday() != entry.day_of_week:
        raise _bad_request(
            f"{subject_name} is taught on {_day_name(entry.day_of_week)}. "
            f"{class_date:%d %b %Y} is a {_day_name(class_date.weekday())}."
        )

    if not is_admin and (today - class_date).days > ATTENDANCE_BACKDATE_DAYS:
        raise _bad_request(
            f"Attendance can only be marked within the last {ATTENDANCE_BACKDATE_DAYS} days. "
            "Ask your admin to correct an older register."
        )

    semester = entry.semester
    if semester and semester.start_date and semester.end_date:
        if not semester.start_date <= class_date <= semester.end_date:
            raise _bad_request(
                f"{class_date:%d %b %Y} is outside {semester.name} "
                f"({semester.start_date:%d %b %Y} – {semester.end_date:%d %b %Y})."
            )

    return class_date


def ensure_can_mark(db: Session, user: User, entry: TimetableEntry) -> None:
    """Admins mark anything; a lecturer marks only what they themselves teach."""
    if user.role == "ADMIN":
        return

    if user.role == "FACULTY":
        from app.services import faculty as faculty_service

        faculty = faculty_service.get_faculty_for_user(db, user.id)
        if entry.faculty_id != faculty.id:
            raise _forbidden("You can only mark attendance for your own classes.")
        return

    raise _forbidden("Only staff can mark attendance.")


def get_session_or_404(db: Session, session_id: int) -> AttendanceSession:
    session = (
        db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    )
    if not session:
        raise _not_found("Attendance session not found.")
    return session


def find_session(
    db: Session, timetable_entry_id: int, class_date: date
) -> AttendanceSession | None:
    return (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.timetable_entry_id == timetable_entry_id,
            AttendanceSession.class_date == class_date,
        )
        .first()
    )


def roster_for_entry(db: Session, entry: TimetableEntry) -> list[Student]:
    """The section's ACTIVE students, in roll-number order.

    Only ever used to BUILD a sheet. Nothing that reads a saved register
    filters on status, or a student suspended later would lose the attendance
    they had already earned.
    """
    from app.services import student_service

    return student_service.list_students(
        db, section_id=entry.section_id, student_status="ACTIVE"
    )


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def _counts(records) -> dict:
    """Tally a list of records or record-outs by status."""
    tally = {"PRESENT": 0, "ABSENT": 0, "LATE": 0, "EXCUSED": 0}
    for record in records:
        status = (record.status or "").upper()
        if status in tally:
            tally[status] += 1

    total = sum(tally.values())
    excused = sum(tally[s] for s in EXCUSED_STATUSES)
    present = sum(tally[s] for s in PRESENT_STATUSES)
    countable = total - excused

    return {
        "total": total,
        "present_count": present,
        "absent_count": tally["ABSENT"],
        "late_count": tally["LATE"],
        "excused_count": excused,
        "countable_count": countable,
        "attendance_percentage": percentage(present, countable),
    }


def percentage(present: int, countable: int) -> float:
    if not countable:
        return 0.0
    return round((present / countable) * 100, 2)


def standing(countable: int, value: float, threshold: float) -> str:
    if not countable:
        return "NO_DATA"
    if value < threshold:
        return "SHORT"
    if value < threshold + 5:
        return "AT_RISK"
    return "GOOD"


def serialize_record(record: AttendanceRecord) -> AttendanceRecordOut:
    student = record.student
    section = student.section if student else None
    user = student.user if student else None

    return AttendanceRecordOut(
        id=record.id,
        attendance_session_id=record.attendance_session_id,
        student_id=record.student_id,
        section_id=record.section_id,
        status=record.status,
        remarks=record.remarks,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
        student_code=student.student_id if student else None,
        student_name=_student_name(student),
        student_email=user.email if user else None,
        student_status=student.status if student else None,
        student_section_id=student.section_id if student else None,
        student_section_name=section.name if section else None,
        is_present=(record.status or "").upper() in PRESENT_STATUSES,
        moved_section=bool(student and student.section_id != record.section_id),
    )


def draft_record(student: Student) -> AttendanceRecordOut:
    """A roster row that has never been saved."""
    section = student.section

    return AttendanceRecordOut(
        id=None,
        attendance_session_id=None,
        student_id=student.id,
        section_id=student.section_id,
        status=DEFAULT_RECORD_STATUS,
        remarks=None,
        student_code=student.student_id,
        student_name=_student_name(student),
        student_email=student.user.email if student.user else None,
        student_status=student.status,
        student_section_id=student.section_id,
        student_section_name=section.name if section else None,
        is_present=DEFAULT_RECORD_STATUS in PRESENT_STATUSES,
        moved_section=False,
    )


def serialize_session(session: AttendanceSession) -> AttendanceSessionOut:
    from app.services import timetable_service

    entry = session.timetable_entry
    subject = session.subject
    faculty = session.faculty
    section = session.section
    semester = session.semester
    slot = session.time_slot
    course = subject.course if subject else None
    department = course.department if course else None
    academic_year = semester.academic_year if semester else None
    marker = session.marked_by

    home_room = timetable_service.normalize_room(section.room_number) if section else None
    room = timetable_service.effective_room(entry.room_number, section) if entry else home_room

    counts = _counts(session.records)
    cancelled = _is_cancelled(session)

    return AttendanceSessionOut(
        id=session.id,
        timetable_entry_id=session.timetable_entry_id,
        teaching_assignment_id=session.teaching_assignment_id,
        faculty_id=session.faculty_id,
        subject_id=session.subject_id,
        section_id=session.section_id,
        semester_id=session.semester_id,
        time_slot_id=session.time_slot_id,
        class_date=session.class_date,
        day_of_week=session.day_of_week,
        session_status=session.session_status,
        cancel_reason=session.cancel_reason,
        notes=session.notes,
        marked_by_user_id=session.marked_by_user_id,
        marked_at=session.marked_at,
        is_active=session.is_active,
        created_at=session.created_at,
        updated_at=session.updated_at,
        day_name=_day_name(session.day_of_week),
        period_number=slot.period_number if slot else None,
        slot_name=slot.name if slot else None,
        start_time=timetable_service._hhmm(slot.start_time) if slot else None,
        end_time=timetable_service._hhmm(slot.end_time) if slot else None,
        slot_label=timetable_service._slot_label(slot),
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        faculty_name=_faculty_name(faculty),
        faculty_code=faculty.faculty_id if faculty else None,
        faculty_department_id=faculty.department_id if faculty else None,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        section_room_number=home_room,
        room_number=room,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=course.id if course else None,
        course_name=course.name if course else None,
        course_code=course.code if course else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        academic_year_id=academic_year.id if academic_year else None,
        academic_year_name=academic_year.name if academic_year else None,
        marked_by_name=marker.email if marker else None,
        marked_by_role=marker.role if marker else None,
        total_students=counts["total"],
        present_count=counts["present_count"],
        absent_count=counts["absent_count"],
        late_count=counts["late_count"],
        excused_count=counts["excused_count"],
        countable_count=counts["countable_count"],
        attendance_percentage=counts["attendance_percentage"],
        is_cancelled=cancelled,
    )


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------

def build_sheet(
    db: Session, user: User, timetable_entry_id: int, class_date: date
) -> AttendanceSheet:
    """The marking screen for one class on one date.

    Read-only by design. The session row is the denominator of every
    percentage in the system, so it is created by SAVING a sheet, never by
    opening one.
    """
    session = find_session(db, timetable_entry_id, class_date)
    entry = resolve_entry(db, timetable_entry_id, for_new_session=session is None)
    ensure_can_mark(db, user, entry)
    validate_class_date(db, entry, class_date, is_admin=user.role == "ADMIN")

    assignment = entry.teaching_assignment
    subject = assignment.subject if assignment else None
    section = entry.section
    faculty = entry.faculty
    slot = entry.time_slot

    from app.services import timetable_service

    roster = roster_for_entry(db, entry)
    records: list[AttendanceRecordOut] = []
    sheet_state = "DRAFT"
    editable = True
    locked_reason = None

    if session and _is_cancelled(session):
        # A cancelled class has no attendance, so it has no roster to show.
        # Prefilling it with default-PRESENT drafts would report a full house
        # for a class that never happened.
        sheet_state = "CANCELLED"
        locked_reason = session.cancel_reason or "This class was cancelled."
    elif session:
        marked_ids = set()
        for record in sorted(
            session.records,
            key=lambda r: ((r.student.student_id or "") if r.student else "", r.student_id),
        ):
            records.append(serialize_record(record))
            marked_ids.add(record.student_id)

        # A student admitted after the sheet was marked must be markable, not
        # invisible — otherwise they are quietly absent from every report.
        for student in roster:
            if student.id not in marked_ids:
                records.append(draft_record(student))

        sheet_state = "MARKED"
    else:
        records = [draft_record(student) for student in roster]

    if not records and sheet_state != "CANCELLED":
        editable = False
        locked_reason = "This section has no active students."

    counts = _counts(records)

    return AttendanceSheet(
        timetable_entry_id=entry.id,
        class_date=class_date,
        day_name=_day_name(entry.day_of_week),
        session=serialize_session(session) if session else None,
        records=records,
        sheet_state=sheet_state,
        editable=editable,
        locked_reason=locked_reason,
        subject_id=subject.id if subject else None,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        section_id=section.id if section else None,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        faculty_id=faculty.id if faculty else None,
        faculty_name=_faculty_name(faculty),
        slot_name=slot.name if slot else None,
        slot_label=timetable_service._slot_label(slot),
        room_number=timetable_service.effective_room(entry.room_number, section),
        total_students=counts["total"],
        present_count=counts["present_count"],
        absent_count=counts["absent_count"],
        late_count=counts["late_count"],
        excused_count=counts["excused_count"],
        countable_count=counts["countable_count"],
        attendance_percentage=counts["attendance_percentage"],
    )


def save_sheet(db: Session, user: User, payload: AttendanceSheetSave) -> AttendanceSession:
    """Create or correct one register. Saving twice corrects, never duplicates."""
    session = find_session(db, payload.timetable_entry_id, payload.class_date)
    entry = resolve_entry(db, payload.timetable_entry_id, for_new_session=session is None)
    ensure_can_mark(db, user, entry)
    validate_class_date(db, entry, payload.class_date, is_admin=user.role == "ADMIN")

    assignment = entry.teaching_assignment
    subject = assignment.subject if assignment else None
    section = entry.section

    session_status = validate_session_status(payload.session_status)
    cancel_reason = (payload.cancel_reason or "").strip() or None
    if session_status == "CANCELLED" and not cancel_reason:
        raise _bad_request("Say why the class was cancelled.")
    if session_status == "HELD":
        cancel_reason = None

    # The roster, plus anyone already holding a record — so a student who has
    # since gone INACTIVE can still have their existing row corrected.
    markable = {student.id: student for student in roster_for_entry(db, entry)}
    if session:
        for record in session.records:
            if record.student and record.student_id not in markable:
                markable[record.student_id] = record.student

    # Validate the whole payload before touching the database.
    cleaned: list[tuple[Student, str, str | None]] = []
    if session_status == "HELD":
        seen: set[int] = set()
        for item in payload.records:
            student = markable.get(item.student_id)
            if not student:
                raise _bad_request(
                    f"Student {item.student_id} is not in "
                    f"{section.name if section else 'this section'}."
                )
            if item.student_id in seen:
                raise _bad_request(f"{_student_name(student)} appears twice on this sheet.")
            seen.add(item.student_id)
            cleaned.append(
                (student, validate_record_status(item.status), (item.remarks or "").strip() or None)
            )

        if markable and not cleaned:
            raise _bad_request("Mark at least one student before saving.")

    try:
        if session is None:
            session = AttendanceSession(
                timetable_entry_id=entry.id,
                # Every identity field is copied from the entry, never taken
                # from the client — forging someone else's class is impossible.
                teaching_assignment_id=entry.teaching_assignment_id,
                faculty_id=entry.faculty_id,
                subject_id=subject.id,
                section_id=entry.section_id,
                semester_id=entry.semester_id,
                time_slot_id=entry.time_slot_id,
                class_date=payload.class_date,
                day_of_week=entry.day_of_week,
            )
            db.add(session)

        session.session_status = session_status
        session.cancel_reason = cancel_reason
        session.notes = (payload.notes or "").strip() or None
        session.marked_by_user_id = user.id
        session.marked_at = func.now()
        db.flush()

        existing = {record.student_id: record for record in session.records}

        if session_status == "CANCELLED":
            # A cancelled class has no attendance. Leaving stale PRESENT rows
            # behind would let them re-enter a denominator if the status were
            # ever flipped back by mistake.
            for record in list(session.records):
                db.delete(record)
        else:
            for student, status, remarks in cleaned:
                record = existing.get(student.id)
                if record:
                    record.status = status
                    record.remarks = remarks
                    record.section_id = student.section_id
                else:
                    db.add(
                        AttendanceRecord(
                            attendance_session_id=session.id,
                            student_id=student.id,
                            section_id=student.section_id,
                            status=status,
                            remarks=remarks,
                        )
                    )

        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict(
            f"Attendance for {subject.name if subject else 'this class'} on "
            f"{payload.class_date:%d %b %Y} was just saved by someone else. "
            "Reload the sheet and try again."
        )
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not save attendance. Please try again.")

    db.refresh(session)
    return session


def set_session_status(
    db: Session, session: AttendanceSession, payload: AttendanceSessionStatusUpdate
) -> AttendanceSession:
    status = validate_session_status(payload.session_status)
    cancel_reason = (payload.cancel_reason or "").strip() or None

    if status == "CANCELLED" and not cancel_reason:
        raise _bad_request("Say why the class was cancelled.")

    session.session_status = status
    session.cancel_reason = cancel_reason if status == "CANCELLED" else None

    if status == "CANCELLED":
        for record in list(session.records):
            db.delete(record)

    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session: AttendanceSession) -> None:
    """Hard delete. The records go with it through the cascade."""
    db.delete(session)
    db.commit()


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_sessions(
    db: Session,
    timetable_entry_id: int | None = None,
    teaching_assignment_id: int | None = None,
    faculty_id: int | None = None,
    subject_id: int | None = None,
    section_id: int | None = None,
    semester_id: int | None = None,
    course_id: int | None = None,
    department_id: int | None = None,
    academic_year_id: int | None = None,
    student_id: int | None = None,
    class_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    session_status: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[AttendanceSession]:
    query = (
        db.query(AttendanceSession)
        .join(Subject, AttendanceSession.subject_id == Subject.id)
        .join(Course, Subject.course_id == Course.id)
        .join(Section, AttendanceSession.section_id == Section.id)
        .join(Semester, AttendanceSession.semester_id == Semester.id)
        .join(Faculty, AttendanceSession.faculty_id == Faculty.id)
        .join(TimeSlot, AttendanceSession.time_slot_id == TimeSlot.id)
        .options(
            joinedload(AttendanceSession.subject).joinedload(Subject.course),
            joinedload(AttendanceSession.section),
            joinedload(AttendanceSession.faculty),
            joinedload(AttendanceSession.semester),
            joinedload(AttendanceSession.time_slot),
            joinedload(AttendanceSession.timetable_entry),
            joinedload(AttendanceSession.marked_by),
            joinedload(AttendanceSession.records),
        )
    )

    if timetable_entry_id is not None:
        query = query.filter(AttendanceSession.timetable_entry_id == timetable_entry_id)
    if teaching_assignment_id is not None:
        query = query.filter(AttendanceSession.teaching_assignment_id == teaching_assignment_id)
    if faculty_id is not None:
        query = query.filter(AttendanceSession.faculty_id == faculty_id)
    if subject_id is not None:
        query = query.filter(AttendanceSession.subject_id == subject_id)
    if section_id is not None:
        query = query.filter(AttendanceSession.section_id == section_id)
    if semester_id is not None:
        query = query.filter(AttendanceSession.semester_id == semester_id)
    if course_id is not None:
        query = query.filter(Subject.course_id == course_id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if class_date is not None:
        query = query.filter(AttendanceSession.class_date == class_date)
    if from_date is not None:
        query = query.filter(AttendanceSession.class_date >= from_date)
    if to_date is not None:
        query = query.filter(AttendanceSession.class_date <= to_date)
    if session_status:
        query = query.filter(AttendanceSession.session_status == session_status.strip().upper())
    if is_active is not None:
        query = query.filter(AttendanceSession.is_active == is_active)
    if student_id is not None:
        query = query.join(
            AttendanceRecord,
            AttendanceRecord.attendance_session_id == AttendanceSession.id,
        ).filter(AttendanceRecord.student_id == student_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Subject.name.ilike(term)
            | Subject.subject_code.ilike(term)
            | Section.name.ilike(term)
            | Faculty.first_name.ilike(term)
            | Faculty.last_name.ilike(term)
        )

    return (
        query.order_by(
            AttendanceSession.class_date.desc(),
            TimeSlot.period_number.asc(),
            Section.name.asc(),
        )
        .all()
    )


def list_markable_classes(
    db: Session, user: User, class_date: date
) -> list[MarkableClassOut]:
    """A lecturer's classes on one date, and which are already marked."""
    from app.services import faculty as faculty_service
    from app.services import timetable_service

    if user.role != "FACULTY":
        raise _bad_request(
            "Admins do not have a personal class list. Filter sessions by section or faculty instead."
        )

    faculty = faculty_service.get_faculty_for_user(db, user.id)

    # No is_active filter: a paused class is SHOWN so it does not look like a
    # missing class, but its sheet refuses to open.
    entries = timetable_service.list_entries(
        db, faculty_id=faculty.id, day_of_week=class_date.weekday()
    )

    rows: list[MarkableClassOut] = []
    for entry in entries:
        session = find_session(db, entry.id, class_date)
        assignment = entry.teaching_assignment
        subject = assignment.subject if assignment else None
        section = entry.section
        slot = entry.time_slot

        counts = _counts(session.records) if session else None
        total_students = (
            counts["total"] if counts and counts["total"] else len(roster_for_entry(db, entry))
        )

        if not entry.is_active and not session:
            status = "PAUSED"
        elif session and _is_cancelled(session):
            status = "CANCELLED"
        elif session:
            status = "MARKED"
        else:
            status = "UNMARKED"

        rows.append(
            MarkableClassOut(
                timetable_entry_id=entry.id,
                teaching_assignment_id=entry.teaching_assignment_id,
                subject_id=subject.id if subject else None,
                subject_code=subject.subject_code if subject else None,
                subject_name=subject.name if subject else None,
                subject_type=subject.subject_type if subject else None,
                section_id=section.id if section else None,
                section_name=section.name if section else None,
                section_code=section.code if section else None,
                faculty_id=entry.faculty_id,
                faculty_name=_faculty_name(entry.faculty),
                time_slot_id=entry.time_slot_id,
                period_number=slot.period_number if slot else None,
                slot_name=slot.name if slot else None,
                start_time=timetable_service._hhmm(slot.start_time) if slot else None,
                end_time=timetable_service._hhmm(slot.end_time) if slot else None,
                slot_label=timetable_service._slot_label(slot),
                room_number=timetable_service.effective_room(entry.room_number, section),
                class_date=class_date,
                day_of_week=entry.day_of_week,
                day_name=_day_name(entry.day_of_week),
                entry_is_active=entry.is_active,
                session_id=session.id if session else None,
                session_status=session.session_status if session else None,
                marked=session is not None,
                marked_at=session.marked_at if session else None,
                marked_by_name=(
                    session.marked_by.email if session and session.marked_by else None
                ),
                total_students=total_students,
                present_count=counts["present_count"] if counts else 0,
                attendance_percentage=counts["attendance_percentage"] if counts else 0.0,
                status=status,
            )
        )

    rows.sort(key=lambda r: (r.period_number or 0, r.section_name or ""))
    return rows


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def _held_records_query(db: Session):
    """Every record that belongs to a class which actually took place."""
    return (
        db.query(AttendanceRecord, AttendanceSession)
        .join(
            AttendanceSession,
            AttendanceRecord.attendance_session_id == AttendanceSession.id,
        )
        .filter(AttendanceSession.session_status == "HELD")
    )


def student_summary(
    db: Session,
    student: Student,
    from_date: date | None = None,
    to_date: date | None = None,
    threshold: float = DEFAULT_ATTENDANCE_THRESHOLD,
) -> StudentAttendanceSummary:
    """One student's standing, per subject.

    Deliberately not filtered by the student's CURRENT section: a student who
    transferred keeps the records of the section that actually taught them.
    """
    query = _held_records_query(db).filter(AttendanceRecord.student_id == student.id)
    if from_date is not None:
        query = query.filter(AttendanceSession.class_date >= from_date)
    if to_date is not None:
        query = query.filter(AttendanceSession.class_date <= to_date)

    buckets: dict[int, dict] = {}
    for record, session in query.all():
        bucket = buckets.setdefault(
            session.subject_id,
            {"session": session, "records": [], "assignment_id": session.teaching_assignment_id},
        )
        bucket["records"].append(record)

    subjects: list[SubjectAttendanceSummary] = []
    overall_present = overall_countable = overall_held = 0

    for subject_id, bucket in buckets.items():
        counts = _counts(bucket["records"])
        session = bucket["session"]
        subject = session.subject
        faculty = session.faculty
        section = session.section

        held = len(bucket["records"])
        overall_held += held
        overall_present += counts["present_count"]
        overall_countable += counts["countable_count"]

        subjects.append(
            SubjectAttendanceSummary(
                subject_id=subject_id,
                subject_code=subject.subject_code if subject else None,
                subject_name=subject.name if subject else None,
                subject_type=subject.subject_type if subject else None,
                teaching_assignment_id=bucket["assignment_id"],
                faculty_id=session.faculty_id,
                faculty_name=_faculty_name(faculty),
                section_id=session.section_id,
                section_name=section.name if section else None,
                held_sessions=held,
                countable_sessions=counts["countable_count"],
                present_count=counts["present_count"],
                absent_count=counts["absent_count"],
                late_count=counts["late_count"],
                excused_count=counts["excused_count"],
                attendance_percentage=counts["attendance_percentage"],
                status=standing(
                    counts["countable_count"], counts["attendance_percentage"], threshold
                ),
            )
        )

    subjects.sort(key=lambda s: (s.subject_code or ""))

    overall = percentage(overall_present, overall_countable)
    section = student.section
    semester = student.semester

    return StudentAttendanceSummary(
        student_id=student.id,
        student_code=student.student_id,
        student_name=_student_name(student),
        section_id=student.section_id,
        section_name=section.name if section else None,
        semester_id=student.semester_id,
        semester_name=semester.name if semester else None,
        from_date=from_date,
        to_date=to_date,
        threshold=threshold,
        overall_held=overall_held,
        overall_countable=overall_countable,
        overall_present=overall_present,
        overall_percentage=overall,
        status=standing(overall_countable, overall, threshold),
        subjects=subjects,
    )


def summary_for_user(
    db: Session,
    user: User,
    from_date: date | None = None,
    to_date: date | None = None,
    threshold: float = DEFAULT_ATTENDANCE_THRESHOLD,
) -> StudentAttendanceSummary:
    if user.role != "STUDENT":
        raise _bad_request(
            "Only students have a personal attendance record. "
            "Use the section or student report instead."
        )

    from app.services import student_service

    student = student_service.get_student_for_user(db, user.id)
    return student_summary(db, student, from_date=from_date, to_date=to_date, threshold=threshold)


def section_report(
    db: Session,
    section_id: int,
    subject_id: int | None = None,
    teaching_assignment_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    threshold: float = DEFAULT_ATTENDANCE_THRESHOLD,
) -> SectionAttendanceReport:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found.")

    sessions = list_sessions(
        db,
        section_id=section_id,
        subject_id=subject_id,
        teaching_assignment_id=teaching_assignment_id,
        from_date=from_date,
        to_date=to_date,
    )
    held = [s for s in sessions if not _is_cancelled(s)]
    cancelled = len(sessions) - len(held)

    # Grouped by student, over the records of HELD sessions only. Filtered by
    # the RECORD's section, never the student's current one.
    by_student: dict[int, dict] = {}
    for session in held:
        for record in session.records:
            bucket = by_student.setdefault(
                record.student_id, {"student": record.student, "records": []}
            )
            bucket["records"].append(record)

    rows: list[SectionAttendanceRow] = []
    total_present = total_countable = 0

    for student_id, bucket in by_student.items():
        counts = _counts(bucket["records"])
        student = bucket["student"]
        total_present += counts["present_count"]
        total_countable += counts["countable_count"]

        rows.append(
            SectionAttendanceRow(
                student_id=student_id,
                student_code=student.student_id if student else None,
                student_name=_student_name(student),
                student_status=student.status if student else None,
                held_sessions=len(bucket["records"]),
                countable_sessions=counts["countable_count"],
                present_count=counts["present_count"],
                absent_count=counts["absent_count"],
                late_count=counts["late_count"],
                excused_count=counts["excused_count"],
                attendance_percentage=counts["attendance_percentage"],
                status=standing(
                    counts["countable_count"], counts["attendance_percentage"], threshold
                ),
            )
        )

    rows.sort(key=lambda r: (r.student_code or ""))

    subject = None
    if subject_id is not None:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()

    semester = section.semester

    return SectionAttendanceReport(
        section_id=section.id,
        section_name=section.name,
        section_code=section.code,
        semester_id=section.semester_id,
        semester_name=semester.name if semester else None,
        subject_id=subject_id,
        subject_name=subject.name if subject else None,
        from_date=from_date,
        to_date=to_date,
        threshold=threshold,
        total_sessions=len(sessions),
        held_sessions=len(held),
        cancelled_sessions=cancelled,
        total_students=len(rows),
        defaulter_count=sum(1 for row in rows if row.status == "SHORT"),
        section_percentage=percentage(total_present, total_countable),
        students=rows,
    )


# --------------------------------------------------------------------------
# counts — the guards that keep a register from being deleted out from under
# --------------------------------------------------------------------------

def count_for_entry(db: Session, timetable_entry_id: int) -> int:
    return (
        db.query(AttendanceSession)
        .filter(AttendanceSession.timetable_entry_id == timetable_entry_id)
        .count()
    )


def count_for_assignment(db: Session, teaching_assignment_id: int) -> int:
    return (
        db.query(AttendanceSession)
        .filter(AttendanceSession.teaching_assignment_id == teaching_assignment_id)
        .count()
    )


def count_for_section(db: Session, section_id: int) -> int:
    return (
        db.query(AttendanceSession)
        .filter(AttendanceSession.section_id == section_id)
        .count()
    )


def count_for_faculty(db: Session, faculty_id: int) -> int:
    return (
        db.query(AttendanceSession).filter(AttendanceSession.faculty_id == faculty_id).count()
    )


def count_for_student(db: Session, student_id: int) -> int:
    return (
        db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student_id).count()
    )
