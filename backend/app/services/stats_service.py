"""Dashboard aggregates.

Everything here is a grouped SQL aggregate. The dashboard this replaces
downloaded five entire tables and called ``len()`` on each, which works on a
demo database and stops working on a real one.

What this module owns: that every number it returns is derived from a real
row, and that "nothing has been marked yet" is reported as such rather than
as a confident zero.
"""

from collections import OrderedDict
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.academic_year import AcademicYear
from app.models.assessment import Assessment
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.course import Course
from app.models.department import Department
from app.models.mark_record import MarkRecord
from app.models.faculty import Faculty
from app.models.section import Section
from app.models.semester import Semester
from app.models.student import Student
from app.models.subject import Subject
from app.models.teaching_assignment import TeachingAssignment
from app.models.time_slot import TimeSlot
from app.models.timetable_entry import TimetableEntry
from app.schemas.assessment import COUNTED_ASSESSMENT_STATUSES, GRADE_SCALE, grade_for
from app.schemas.attendance import EXCUSED_STATUSES, PRESENT_STATUSES
from app.schemas.stats import (
    DEPARTMENT_SLICE_LIMIT,
    MONTHLY_SERIES_MONTHS,
    RECENT_REGISTER_LIMIT,
    SECTION_FILL_LIMIT,
    SUBJECT_RESULT_LIMIT,
    AssessmentStats,
    AttendanceSeries,
    AttendanceStats,
    CountStats,
    DashboardStats,
    DepartmentStudentCount,
    GradeBandCount,
    MonthlyAttendancePoint,
    RecentRegisterRow,
    SectionFillRow,
    SubjectPassRow,
    TodayStats,
)
from app.schemas.timetable import DAY_NAMES

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _percentage(present: int, countable: int) -> float:
    """The one division guard. 0 countable is 'unknown', not 0%."""
    if not countable:
        return 0.0
    return round((present / countable) * 100, 2)


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _month_label(year: int, month: int) -> str:
    return f"{MONTH_LABELS[month - 1]} {year}"


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


# --------------------------------------------------------------------------
# counts
# --------------------------------------------------------------------------

def _count(db: Session, model, *filters) -> int:
    query = db.query(func.count(model.id))
    for condition in filters:
        query = query.filter(condition)
    return query.scalar() or 0


def collect_counts(db: Session) -> CountStats:
    return CountStats(
        departments=_count(db, Department),
        courses=_count(db, Course),
        academic_years=_count(db, AcademicYear),
        semesters=_count(db, Semester),
        sections=_count(db, Section),
        faculty=_count(db, Faculty),
        active_faculty=_count(db, Faculty, Faculty.is_active.is_(True)),
        students=_count(db, Student),
        active_students=_count(db, Student, Student.status == "ACTIVE"),
        subjects=_count(db, Subject),
        teaching_assignments=_count(db, TeachingAssignment),
        timetable_entries=_count(db, TimetableEntry),
    )


def students_by_department(db: Session) -> list[DepartmentStudentCount]:
    """Every department with its head count, largest first.

    A LEFT JOIN so a department with no students still appears — the UI shows
    it at zero rather than pretending it does not exist.
    """
    rows = (
        db.query(
            Department.id,
            Department.code,
            Department.name,
            func.count(Student.id).label("student_count"),
        )
        .outerjoin(Student, Student.department_id == Department.id)
        .group_by(Department.id, Department.code, Department.name)
        .order_by(func.count(Student.id).desc(), Department.name.asc())
        .all()
    )

    return [
        DepartmentStudentCount(
            department_id=row[0],
            department_code=row[1],
            department_name=row[2],
            student_count=row[3] or 0,
        )
        for row in rows
    ]


# --------------------------------------------------------------------------
# attendance
# --------------------------------------------------------------------------

def _status_totals(db: Session, *filters) -> dict:
    """Records grouped by status, over HELD sessions only.

    A cancelled class counts toward nobody, so it never reaches this query.
    """
    query = (
        db.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .join(
            AttendanceSession,
            AttendanceRecord.attendance_session_id == AttendanceSession.id,
        )
        .filter(AttendanceSession.session_status == "HELD")
    )
    for condition in filters:
        query = query.filter(condition)

    tally = {"PRESENT": 0, "ABSENT": 0, "LATE": 0, "EXCUSED": 0}
    for status, count in query.group_by(AttendanceRecord.status).all():
        key = (status or "").upper()
        if key in tally:
            tally[key] = count or 0
    return tally


def _summarize(tally: dict) -> dict:
    total = sum(tally.values())
    excused = sum(tally[s] for s in EXCUSED_STATUSES)
    present = sum(tally[s] for s in PRESENT_STATUSES)
    countable = total - excused
    return {
        "present": present,
        "absent": tally["ABSENT"],
        "late": tally["LATE"],
        "excused": excused,
        "countable": countable,
    }


def collect_attendance(db: Session) -> AttendanceStats:
    tally = _status_totals(db)
    totals = _summarize(tally)

    held = _count(db, AttendanceSession, AttendanceSession.session_status == "HELD")
    cancelled = _count(
        db, AttendanceSession, AttendanceSession.session_status == "CANCELLED"
    )

    bounds = (
        db.query(
            func.min(AttendanceSession.class_date), func.max(AttendanceSession.class_date)
        )
        .filter(AttendanceSession.session_status == "HELD")
        .first()
    )
    from_date, to_date = (bounds or (None, None))

    return AttendanceStats(
        from_date=from_date,
        to_date=to_date,
        held_sessions=held,
        cancelled_sessions=cancelled,
        present_count=totals["present"],
        absent_count=totals["absent"],
        late_count=totals["late"],
        excused_count=totals["excused"],
        countable_count=totals["countable"],
        attendance_percentage=_percentage(totals["present"], totals["countable"]),
        has_data=held > 0,
    )


def collect_series(db: Session) -> AttendanceSeries:
    """Attendance by month, anchored on the newest month that has data.

    Anchoring on the data rather than on today is what keeps a college whose
    term ended last year from rendering twelve empty buckets — the chart says
    "these twelve months, ending here", and the UI says when "here" was.
    """
    newest = (
        db.query(func.max(AttendanceSession.class_date))
        .filter(AttendanceSession.session_status == "HELD")
        .scalar()
    )
    if not newest:
        return AttendanceSeries(months=[], has_data=False, is_current_period=False)

    anchor_year, anchor_month = newest.year, newest.month

    # Build the window first so a month with no classes is still a bucket,
    # not a gap the chart has to guess at.
    buckets: "OrderedDict[str, dict]" = OrderedDict()
    for offset in range(MONTHLY_SERIES_MONTHS - 1, -1, -1):
        year, month = _shift_month(anchor_year, anchor_month, -offset)
        buckets[f"{year:04d}-{month:02d}"] = {
            "label": _month_label(year, month),
            "held": 0,
            "present": 0,
            "countable": 0,
        }

    first_key = next(iter(buckets))
    start_year, start_month = int(first_key[:4]), int(first_key[5:])
    window_start = date(start_year, start_month, 1)

    # Sessions per month.
    session_rows = (
        db.query(AttendanceSession.class_date, func.count(AttendanceSession.id))
        .filter(
            AttendanceSession.session_status == "HELD",
            AttendanceSession.class_date >= window_start,
        )
        .group_by(AttendanceSession.class_date)
        .all()
    )
    for class_date, count in session_rows:
        key = _month_key(class_date)
        if key in buckets:
            buckets[key]["held"] += count or 0

    # Records per month per status, so the percentage is computed the same
    # way it is everywhere else: (PRESENT + LATE) / (all - EXCUSED).
    record_rows = (
        db.query(
            AttendanceSession.class_date,
            AttendanceRecord.status,
            func.count(AttendanceRecord.id),
        )
        .join(
            AttendanceSession,
            AttendanceRecord.attendance_session_id == AttendanceSession.id,
        )
        .filter(
            AttendanceSession.session_status == "HELD",
            AttendanceSession.class_date >= window_start,
        )
        .group_by(AttendanceSession.class_date, AttendanceRecord.status)
        .all()
    )
    for class_date, status, count in record_rows:
        key = _month_key(class_date)
        if key not in buckets:
            continue
        value = count or 0
        upper = (status or "").upper()
        if upper in PRESENT_STATUSES:
            buckets[key]["present"] += value
        if upper not in EXCUSED_STATUSES:
            buckets[key]["countable"] += value

    months = [
        MonthlyAttendancePoint(
            month=key,
            label=data["label"],
            held_sessions=data["held"],
            present_count=data["present"],
            countable_count=data["countable"],
            attendance_percentage=_percentage(data["present"], data["countable"]),
            has_data=data["held"] > 0,
        )
        for key, data in buckets.items()
    ]

    today = date.today()
    anchor_key = f"{anchor_year:04d}-{anchor_month:02d}"

    return AttendanceSeries(
        months=months,
        anchor_month=anchor_key,
        anchor_label=_month_label(anchor_year, anchor_month),
        is_current_period=(anchor_year == today.year and anchor_month == today.month),
        has_data=any(point.has_data for point in months),
    )


def collect_today(db: Session, today: date | None = None) -> TodayStats:
    class_date = today or date.today()
    day_of_week = class_date.weekday()

    scheduled = _count(
        db,
        TimetableEntry,
        TimetableEntry.day_of_week == day_of_week,
        TimetableEntry.is_active.is_(True),
    )
    marked = _count(
        db,
        AttendanceSession,
        AttendanceSession.class_date == class_date,
        AttendanceSession.session_status == "HELD",
    )
    cancelled = _count(
        db,
        AttendanceSession,
        AttendanceSession.class_date == class_date,
        AttendanceSession.session_status == "CANCELLED",
    )

    return TodayStats(
        class_date=class_date,
        day_of_week=day_of_week,
        day_name=DAY_NAMES[day_of_week] if 0 <= day_of_week < len(DAY_NAMES) else None,
        scheduled_classes=scheduled,
        marked_sessions=marked,
        cancelled_sessions=cancelled,
        # Never negative: an admin can mark a class that was scheduled and
        # later paused, which would otherwise read as -1 still to mark.
        unmarked_classes=max(0, scheduled - marked - cancelled),
    )


# --------------------------------------------------------------------------
# rooms and registers
# --------------------------------------------------------------------------

def collect_section_fill(db: Session) -> list[SectionFillRow]:
    rows = (
        db.query(
            Section.id,
            Section.name,
            Section.code,
            Section.capacity,
            Semester.name,
            func.count(Student.id).label("enrolled"),
        )
        .outerjoin(Student, Student.section_id == Section.id)
        .outerjoin(Semester, Section.semester_id == Semester.id)
        .group_by(Section.id, Section.name, Section.code, Section.capacity, Semester.name)
        .order_by(func.count(Student.id).desc(), Section.name.asc())
        .limit(SECTION_FILL_LIMIT)
        .all()
    )

    result = []
    for section_id, name, code, capacity, semester_name, enrolled in rows:
        capacity = capacity or 0
        enrolled = enrolled or 0
        result.append(
            SectionFillRow(
                section_id=section_id,
                section_name=name,
                section_code=code,
                semester_name=semester_name,
                capacity=capacity,
                enrolled=enrolled,
                fill_percentage=_percentage(enrolled, capacity),
                over_capacity=bool(capacity and enrolled > capacity),
            )
        )
    return result


def collect_recent_registers(db: Session) -> list[RecentRegisterRow]:
    """The newest registers, by the date of the CLASS.

    Ordered on class_date rather than marked_at: marked_at is a tz-aware
    column over a SQLite file storing naive datetimes, so it is the wrong
    thing both to sort by and to show.
    """
    from app.services import attendance_service

    sessions = (
        db.query(AttendanceSession)
        .order_by(AttendanceSession.class_date.desc(), AttendanceSession.id.desc())
        .limit(RECENT_REGISTER_LIMIT)
        .all()
    )

    rows = []
    for session in sessions:
        subject = session.subject
        section = session.section
        faculty = session.faculty
        counts = attendance_service._counts(session.records)

        rows.append(
            RecentRegisterRow(
                session_id=session.id,
                class_date=session.class_date,
                day_name=(
                    DAY_NAMES[session.day_of_week]
                    if 0 <= session.day_of_week < len(DAY_NAMES)
                    else None
                ),
                subject_code=subject.subject_code if subject else None,
                subject_name=subject.name if subject else None,
                section_name=section.name if section else None,
                section_code=section.code if section else None,
                faculty_name=(
                    f"{faculty.first_name} {faculty.last_name}".strip() if faculty else None
                ),
                session_status=session.session_status,
                present_count=counts["present_count"],
                countable_count=counts["countable_count"],
                attendance_percentage=counts["attendance_percentage"],
            )
        )
    return rows


def count_unscheduled_assignments(db: Session) -> int:
    """Active teaching assignments with nothing on the timetable."""
    scheduled = db.query(TimetableEntry.teaching_assignment_id).distinct()
    return (
        db.query(func.count(TeachingAssignment.id))
        .filter(
            TeachingAssignment.is_active.is_(True),
            ~TeachingAssignment.id.in_(scheduled),
        )
        .scalar()
        or 0
    )


# --------------------------------------------------------------------------
# assessments
# --------------------------------------------------------------------------

def collect_assessments(db: Session) -> AssessmentStats:
    """What the assessments module knows, stated the way results states it.

    The grades here are NOT recomputed. Every one comes from
    ``results_service.subject_result``, so the dashboard and the result screen
    can never disagree — and the rules that module enforces (drafts reach
    nobody, an incomplete sheet has no grade) hold here for free.
    """
    from app.services import results_service

    stats = AssessmentStats()

    by_status = dict(
        db.query(Assessment.status, func.count(Assessment.id))
        .filter(Assessment.is_active.is_(True))
        .group_by(Assessment.status)
        .all()
    )
    stats.draft_assessments = by_status.get("DRAFT", 0)
    stats.published_assessments = by_status.get("PUBLISHED", 0)
    stats.locked_assessments = by_status.get("LOCKED", 0)
    stats.total_assessments = sum(by_status.values())
    stats.marks_recorded = db.query(func.count(MarkRecord.id)).scalar() or 0

    counted = (
        db.query(Assessment)
        .filter(
            Assessment.is_active.is_(True),
            Assessment.status.in_(COUNTED_ASSESSMENT_STATUSES),
        )
        .all()
    )
    if not counted:
        return stats

    # Rosters and entered counts, in two queries rather than two per row.
    section_ids = [item.section_id for item in counted]
    rosters = dict(
        db.query(Student.section_id, func.count(Student.id))
        .filter(Student.section_id.in_(set(section_ids)), Student.status == "ACTIVE")
        .group_by(Student.section_id)
        .all()
    )
    entered = dict(
        db.query(MarkRecord.assessment_id, func.count(MarkRecord.id))
        .filter(MarkRecord.assessment_id.in_({item.id for item in counted}))
        .group_by(MarkRecord.assessment_id)
        .all()
    )
    stats.incomplete_sheets = sum(
        1
        for item in counted
        if entered.get(item.id, 0) < rosters.get(item.section_id, 0)
    )

    # One (section, subject) pair is one taught class.
    by_class: dict[tuple[int, int], list] = {}
    for item in counted:
        by_class.setdefault((item.section_id, item.subject_id), []).append(item)

    marks = results_service._marks_by_assessment(db, [item.id for item in counted])
    rows: list[SubjectPassRow] = []
    percents: list[float] = []

    for (section_id, subject_id), group in by_class.items():
        roster = results_service._roster(db, section_id)
        graded = [
            outcome
            for outcome in (
                results_service.subject_result(student.id, group, marks)
                for student in roster
            )
            if outcome.has_data
        ]
        if not graded:
            continue

        first = group[0]
        passed = sum(1 for outcome in graded if outcome.is_pass)
        class_percents = [outcome.percent or 0.0 for outcome in graded]
        percents.extend(class_percents)

        rows.append(
            SubjectPassRow(
                subject_id=subject_id,
                subject_code=first.subject.subject_code if first.subject else None,
                subject_name=first.subject.name if first.subject else None,
                section_id=section_id,
                section_name=first.section.name if first.section else None,
                faculty_name=(
                    f"{first.faculty.first_name} {first.faculty.last_name}".strip()
                    if first.faculty
                    else None
                ),
                graded_students=len(graded),
                pass_count=passed,
                fail_count=len(graded) - passed,
                pass_percentage=round(passed * 100.0 / len(graded), 2),
                average_percent=round(sum(class_percents) / len(class_percents), 2),
            )
        )

    if not percents:
        return stats

    stats.graded_results = len(percents)
    stats.pass_count = sum(row.pass_count for row in rows)
    stats.fail_count = sum(row.fail_count for row in rows)
    stats.pass_percentage = _percentage(stats.pass_count, stats.graded_results)

    bands = {
        letter: GradeBandCount(grade_letter=letter, grade_point=point)
        for _, letter, point in GRADE_SCALE
    }
    for percent in percents:
        letter, _ = grade_for(percent)
        if letter in bands:
            bands[letter].student_count += 1
    for band in bands.values():
        band.percentage = round(band.student_count * 100.0 / len(percents), 2)
    stats.distribution = [bands[letter] for _, letter, _ in GRADE_SCALE]

    # Worst pass rate first — the classes an admin would actually act on.
    rows.sort(key=lambda row: (row.pass_percentage, row.average_percent or 0.0))
    stats.weakest_subjects = rows[:SUBJECT_RESULT_LIMIT]
    stats.has_data = True
    return stats


# --------------------------------------------------------------------------
# the whole page
# --------------------------------------------------------------------------

def dashboard(db: Session) -> DashboardStats:
    return DashboardStats(
        generated_at=datetime.now(),
        counts=collect_counts(db),
        students_by_department=students_by_department(db),
        attendance=collect_attendance(db),
        attendance_series=collect_series(db),
        today=collect_today(db),
        section_fill=collect_section_fill(db),
        recent_registers=collect_recent_registers(db),
        assessments=collect_assessments(db),
        unscheduled_assignments=count_unscheduled_assignments(db),
    )
