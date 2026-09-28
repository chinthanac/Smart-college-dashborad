"""Weekly class schedule.

An entry places an existing teaching assignment on a (day, period) cell, so
"who teaches what to whom" is settled before scheduling ever begins and cannot
be contradicted here. What this module owns is the three ways a schedule can
contradict itself:

  * a faculty member cannot be in two rooms at once — checked across every
    department, because cross-department teaching is legal in this system and
    a department-scoped check would miss the most likely double-booking;
  * a section cannot attend two classes at once;
  * a room cannot hold two classes at once.

None of the three filter on ``is_active``. A deactivated entry still occupies
its cell, exactly as an inactive teaching assignment still occupies its
subject/section pair, and the error routes the admin to the existing row
rather than leaving them stuck behind an invisible obstacle.
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
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.models.user import User
from app.schemas.timetable import (
    DAY_NAMES,
    SectionCoverage,
    SubjectCoverage,
    TimetableCopyDay,
    TimetableCopySkipped,
    TimetableEntryCreate,
    TimetableEntryOut,
    TimetableEntryUpdate,
)
from app.services import faculty as faculty_service
from app.services import student_service


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


def _hhmm(value) -> str | None:
    return value.strftime("%H:%M") if value else None


def _slot_label(slot: TimeSlot | None) -> str | None:
    if not slot:
        return None
    return f"{slot.name} ({_hhmm(slot.start_time)} – {_hhmm(slot.end_time)})"


def _day_name(day_of_week: int | None) -> str | None:
    if day_of_week is None or not 0 <= day_of_week < len(DAY_NAMES):
        return None
    return DAY_NAMES[day_of_week]


def normalize_room(value: str | None) -> str | None:
    room = (value or "").strip()
    return room or None


def _room_key(value: str | None) -> str | None:
    """Rooms are typed by hand, so "L-204", "l 204" and "L204" are one room.

    Everything but letters and digits is dropped. That errs towards reporting
    a clash rather than missing one, which is the right way round: a false
    clash is visible and the admin can rename the room, while a missed one
    puts two classes in the same place and nobody finds out until they walk in.
    """
    room = normalize_room(value)
    if not room:
        return None
    return "".join(character for character in room if character.isalnum()).upper()


def effective_room(entry_room: str | None, section: Section | None) -> str | None:
    """A blank room means "the section's own classroom"."""
    return normalize_room(entry_room) or (normalize_room(section.room_number) if section else None)


def _describe(entry: TimetableEntry) -> str:
    subject = entry.teaching_assignment.subject if entry.teaching_assignment else None
    section = entry.section
    subject_name = subject.name if subject else "another class"
    section_name = section.name if section else "another section"
    return f"{subject_name} ({section_name})"


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def resolve_assignment(db: Session, teaching_assignment_id: int) -> TeachingAssignment:
    assignment = (
        db.query(TeachingAssignment)
        .filter(TeachingAssignment.id == teaching_assignment_id)
        .first()
    )
    if not assignment:
        raise _not_found("Teaching assignment not found")
    if not assignment.is_active:
        raise _bad_request(
            "This teaching assignment is paused and cannot be scheduled. "
            "Reactivate it first."
        )
    if not assignment.section or not assignment.section.is_active:
        raise _bad_request("The section for this assignment is inactive and cannot be scheduled.")
    if not assignment.subject or not assignment.subject.is_active:
        raise _bad_request("The subject for this assignment is inactive and cannot be scheduled.")
    return assignment


def resolve_slot(db: Session, time_slot_id: int) -> TimeSlot:
    slot = db.query(TimeSlot).filter(TimeSlot.id == time_slot_id).first()
    if not slot:
        raise _not_found("Time slot not found")
    if not slot.is_active:
        raise _bad_request("This period is not part of the current schedule.")
    if slot.is_break:
        raise _bad_request(f"{slot.name} is a break and cannot hold a class.")
    return slot


def check_clashes(
    db: Session,
    faculty_id: int,
    section_id: int,
    day_of_week: int,
    time_slot_id: int,
    room: str | None,
    exclude_id: int | None = None,
) -> None:
    """The three rules, evaluated over the one (day, period) cell.

    A single query fetches the cell — at most one row per section in the
    college — so all three checks can name the class they collided with,
    which is the only thing that tells the admin what to move.
    """
    query = db.query(TimetableEntry).filter(
        TimetableEntry.day_of_week == day_of_week,
        TimetableEntry.time_slot_id == time_slot_id,
    )
    if exclude_id is not None:
        query = query.filter(TimetableEntry.id != exclude_id)

    room_key = _room_key(room)

    for other in query.all():
        if other.section_id == section_id:
            raise _conflict(
                f"This section already has {_describe(other)} in this period."
            )

        if other.faculty_id == faculty_id:
            holder = other.faculty
            name = f"{holder.first_name} {holder.last_name}".strip() if holder else "This faculty member"
            raise _conflict(
                f"{name} already teaches {_describe(other)} in this period."
            )

        if room_key and _room_key(effective_room(other.room_number, other.section)) == room_key:
            raise _conflict(
                f"Room {normalize_room(room)} is occupied by {_describe(other)} in this period."
            )


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize(entry: TimetableEntry) -> TimetableEntryOut:
    assignment = entry.teaching_assignment
    subject = assignment.subject if assignment else None
    faculty = entry.faculty
    section = entry.section
    semester = entry.semester
    slot = entry.time_slot
    course = subject.course if subject else None
    department = course.department if course else None
    academic_year = semester.academic_year if semester else None

    room = effective_room(entry.room_number, section)
    home_room = normalize_room(section.room_number) if section else None

    return TimetableEntryOut(
        id=entry.id,
        teaching_assignment_id=entry.teaching_assignment_id,
        faculty_id=entry.faculty_id,
        section_id=entry.section_id,
        semester_id=entry.semester_id,
        day_of_week=entry.day_of_week,
        time_slot_id=entry.time_slot_id,
        room_number=room,
        is_active=entry.is_active,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        day_name=_day_name(entry.day_of_week),
        period_number=slot.period_number if slot else None,
        slot_name=slot.name if slot else None,
        start_time=_hhmm(slot.start_time) if slot else None,
        end_time=_hhmm(slot.end_time) if slot else None,
        slot_label=_slot_label(slot),
        subject_id=subject.id if subject else None,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        subject_credits=subject.credits if subject else None,
        faculty_name=f"{faculty.first_name} {faculty.last_name}".strip() if faculty else None,
        faculty_code=faculty.faculty_id if faculty else None,
        faculty_department_id=faculty.department_id if faculty else None,
        section_name=section.name if section else None,
        section_code=section.code if section else None,
        section_room_number=home_room,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=course.id if course else None,
        course_name=course.name if course else None,
        course_code=course.code if course else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        academic_year_id=academic_year.id if academic_year else None,
        academic_year_name=academic_year.name if academic_year else None,
        is_relocated=bool(room and home_room and _room_key(room) != _room_key(home_room)),
    )


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_entries(
    db: Session,
    section_id: int | None = None,
    faculty_id: int | None = None,
    teaching_assignment_id: int | None = None,
    subject_id: int | None = None,
    semester_id: int | None = None,
    course_id: int | None = None,
    department_id: int | None = None,
    academic_year_id: int | None = None,
    time_slot_id: int | None = None,
    day_of_week: int | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[TimetableEntry]:
    query = (
        db.query(TimetableEntry)
        .join(TeachingAssignment, TimetableEntry.teaching_assignment_id == TeachingAssignment.id)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .join(Course, Subject.course_id == Course.id)
        .join(Faculty, TimetableEntry.faculty_id == Faculty.id)
        .join(Section, TimetableEntry.section_id == Section.id)
        .join(Semester, TimetableEntry.semester_id == Semester.id)
        .join(TimeSlot, TimetableEntry.time_slot_id == TimeSlot.id)
    )

    if section_id is not None:
        query = query.filter(TimetableEntry.section_id == section_id)
    if faculty_id is not None:
        query = query.filter(TimetableEntry.faculty_id == faculty_id)
    if teaching_assignment_id is not None:
        query = query.filter(TimetableEntry.teaching_assignment_id == teaching_assignment_id)
    if subject_id is not None:
        query = query.filter(TeachingAssignment.subject_id == subject_id)
    if semester_id is not None:
        query = query.filter(TimetableEntry.semester_id == semester_id)
    if course_id is not None:
        query = query.filter(Subject.course_id == course_id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if time_slot_id is not None:
        query = query.filter(TimetableEntry.time_slot_id == time_slot_id)
    if day_of_week is not None:
        query = query.filter(TimetableEntry.day_of_week == day_of_week)
    if is_active is not None:
        query = query.filter(TimetableEntry.is_active == is_active)
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
        TimetableEntry.day_of_week.asc(),
        TimeSlot.period_number.asc(),
        Section.name.asc(),
    ).all()


def get_entry_or_404(db: Session, entry_id: int) -> TimetableEntry:
    entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
    if not entry:
        raise _not_found("Timetable entry not found")
    return entry


def list_for_user(
    db: Session,
    user: User,
    day_of_week: int | None = None,
    is_active: bool | None = None,
) -> list[TimetableEntry]:
    """The signed-in user's own week.

    Faculty get everything they teach, including the cross-department classes
    the department-scoped list hides. Students get their section's grid, which
    is their whole timetable — a section attends as one body.
    """
    if user.role == "FACULTY":
        faculty = faculty_service.get_faculty_for_user(db, user.id)
        return list_entries(db, faculty_id=faculty.id, day_of_week=day_of_week, is_active=is_active)

    if user.role == "STUDENT":
        student = student_service.get_student_for_user(db, user.id)
        return list_entries(
            db, section_id=student.section_id, day_of_week=day_of_week, is_active=is_active
        )

    raise _bad_request(
        "Admins do not have a personal timetable. Filter the timetable by section or faculty instead."
    )


def count_for_assignment(db: Session, teaching_assignment_id: int) -> int:
    return (
        db.query(TimetableEntry)
        .filter(TimetableEntry.teaching_assignment_id == teaching_assignment_id)
        .count()
    )


def count_for_section(db: Session, section_id: int) -> int:
    return db.query(TimetableEntry).filter(TimetableEntry.section_id == section_id).count()


def count_for_faculty(db: Session, faculty_id: int) -> int:
    return db.query(TimetableEntry).filter(TimetableEntry.faculty_id == faculty_id).count()


# --------------------------------------------------------------------------
# coverage
# --------------------------------------------------------------------------

def _coverage_status(required: int, scheduled: int) -> str:
    if scheduled > required:
        return "OVER_SCHEDULED"
    if scheduled == required:
        return "COMPLETE"
    if scheduled == 0:
        return "UNSCHEDULED"
    return "UNDER_SCHEDULED"


def section_coverage(db: Session, section_id: int) -> SectionCoverage:
    """Required weekly periods versus what is actually on the grid.

    Subjects have carried lecture/tutorial/practical hours since they were
    introduced and nothing has read them until now. Their sum is the number of
    periods a subject is owed each week, which turns an empty grid into a
    checklist instead of a blank page.
    """
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found")

    assignments = (
        db.query(TeachingAssignment)
        .join(Subject, TeachingAssignment.subject_id == Subject.id)
        .filter(
            TeachingAssignment.section_id == section_id,
            TeachingAssignment.is_active.is_(True),
        )
        .order_by(Subject.subject_code.asc())
        .all()
    )

    subjects: list[SubjectCoverage] = []
    total_required = 0
    total_scheduled = 0

    for assignment in assignments:
        subject = assignment.subject
        faculty = assignment.faculty
        if not subject:
            continue

        required = subject.lecture_hours + subject.tutorial_hours + subject.practical_hours
        scheduled = (
            db.query(TimetableEntry)
            .filter(
                TimetableEntry.teaching_assignment_id == assignment.id,
                TimetableEntry.is_active.is_(True),
            )
            .count()
        )

        total_required += required
        total_scheduled += scheduled

        subjects.append(
            SubjectCoverage(
                teaching_assignment_id=assignment.id,
                subject_id=subject.id,
                subject_code=subject.subject_code,
                subject_name=subject.name,
                subject_type=subject.subject_type,
                faculty_id=assignment.faculty_id,
                faculty_name=f"{faculty.first_name} {faculty.last_name}".strip() if faculty else None,
                lecture_hours=subject.lecture_hours,
                tutorial_hours=subject.tutorial_hours,
                practical_hours=subject.practical_hours,
                required_periods=required,
                scheduled_periods=scheduled,
                remaining_periods=max(required - scheduled, 0),
                status=_coverage_status(required, scheduled),
            )
        )

    semester = section.semester

    return SectionCoverage(
        section_id=section.id,
        section_name=section.name,
        section_code=section.code,
        semester_id=section.semester_id,
        semester_name=semester.name if semester else None,
        total_required=total_required,
        total_scheduled=total_scheduled,
        subjects=subjects,
    )


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_entry(db: Session, payload: TimetableEntryCreate) -> TimetableEntry:
    assignment = resolve_assignment(db, payload.teaching_assignment_id)
    resolve_slot(db, payload.time_slot_id)

    room = normalize_room(payload.room_number)
    check_clashes(
        db,
        faculty_id=assignment.faculty_id,
        section_id=assignment.section_id,
        day_of_week=payload.day_of_week,
        time_slot_id=payload.time_slot_id,
        room=effective_room(room, assignment.section),
    )

    entry = TimetableEntry(
        teaching_assignment_id=assignment.id,
        faculty_id=assignment.faculty_id,
        section_id=assignment.section_id,
        semester_id=assignment.semester_id,
        day_of_week=payload.day_of_week,
        time_slot_id=payload.time_slot_id,
        room_number=room,
        is_active=payload.is_active,
    )

    try:
        db.add(entry)
        db.commit()
    except IntegrityError:
        # The section/day/period constraint can still fire if another admin
        # filled this cell between the check above and this commit.
        db.rollback()
        raise _conflict("This section already has a class in this period.")
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not schedule the class. Please try again.")

    db.refresh(entry)
    return entry


def update_entry(
    db: Session,
    entry: TimetableEntry,
    payload: TimetableEntryUpdate,
) -> TimetableEntry:
    assignment = resolve_assignment(db, payload.teaching_assignment_id)
    resolve_slot(db, payload.time_slot_id)

    room = normalize_room(payload.room_number)
    check_clashes(
        db,
        faculty_id=assignment.faculty_id,
        section_id=assignment.section_id,
        day_of_week=payload.day_of_week,
        time_slot_id=payload.time_slot_id,
        room=effective_room(room, assignment.section),
        exclude_id=entry.id,
    )

    try:
        entry.teaching_assignment_id = assignment.id
        entry.faculty_id = assignment.faculty_id
        entry.section_id = assignment.section_id
        entry.semester_id = assignment.semester_id
        entry.day_of_week = payload.day_of_week
        entry.time_slot_id = payload.time_slot_id
        entry.room_number = room
        entry.is_active = payload.is_active
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("This section already has a class in this period.")
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the class. Please try again.")

    db.refresh(entry)
    return entry


def set_status(db: Session, entry: TimetableEntry, is_active: bool) -> TimetableEntry:
    entry.is_active = is_active
    db.commit()
    db.refresh(entry)
    return entry


def copy_day(
    db: Session,
    payload: TimetableCopyDay,
) -> tuple[list[TimetableEntry], list[TimetableCopySkipped]]:
    """Duplicate one section's day onto another day.

    Most weeks repeat, so this is how a five-day grid gets built from one. A
    period that would clash is reported rather than aborting the batch: the
    normal case is a day that is already partly filled, and losing the rest of
    the copy over one lab slot would be worse than useless.
    """
    if payload.from_day == payload.to_day:
        raise _bad_request("Choose a different day to copy into.")

    section = db.query(Section).filter(Section.id == payload.section_id).first()
    if not section:
        raise _not_found("Section not found")

    source = list_entries(db, section_id=payload.section_id, day_of_week=payload.from_day)
    if not source:
        raise _bad_request(f"{_day_name(payload.from_day)} has no classes to copy.")

    created: list[TimetableEntry] = []
    skipped: list[TimetableCopySkipped] = []
    pending: list[TimetableEntry] = []

    # No cross-checking within the batch is needed: every source row belongs to
    # one section on one day, so the section/day/period constraint has already
    # guaranteed they occupy distinct periods and cannot collide with each other.
    for item in source:
        room = effective_room(item.room_number, item.section)
        conflict: str | None = None

        try:
            check_clashes(
                db,
                faculty_id=item.faculty_id,
                section_id=item.section_id,
                day_of_week=payload.to_day,
                time_slot_id=item.time_slot_id,
                room=room,
            )
        except HTTPException as exc:
            conflict = str(exc.detail)

        if conflict:
            skipped.append(
                TimetableCopySkipped(
                    time_slot_id=item.time_slot_id,
                    slot_label=_slot_label(item.time_slot),
                    reason=conflict,
                )
            )
            continue

        pending.append(
            TimetableEntry(
                teaching_assignment_id=item.teaching_assignment_id,
                faculty_id=item.faculty_id,
                section_id=item.section_id,
                semester_id=item.semester_id,
                day_of_week=payload.to_day,
                time_slot_id=item.time_slot_id,
                room_number=item.room_number,
                is_active=item.is_active,
            )
        )

    if not pending:
        return created, skipped

    try:
        for entry in pending:
            db.add(entry)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _conflict("Another admin scheduled into these periods. Reload and try again.")
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not copy the day. Please try again.")

    for entry in pending:
        db.refresh(entry)
        created.append(entry)

    return created, skipped


def delete_entry(db: Session, entry: TimetableEntry) -> None:
    """Hard delete, but only while nothing remembers the class happening.

    Once attendance references a scheduled class, deleting the entry would take
    the register with it, so the admin is routed to /status instead — which is
    what this docstring has promised since the module was written.
    """
    from app.services import attendance_service

    marked = attendance_service.count_for_entry(db, entry.id)
    if marked:
        raise _conflict(
            f"This class has {marked} attendance session(s) on record. "
            "Pause it instead of deleting it, so the register survives."
        )

    try:
        db.delete(entry)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not remove the class. Please try again.")
