"""Results — derived at read time, never stored.

A stored grade is a second source of truth. Marks are corrected constantly, and
the moment one is, a stored row is wrong until something recomputes it — and
nothing guarantees that something runs. Derivation is cheap here and it is
always right.

The formula, for one student in one subject::

    subject_percent = sum over counted assessments of
                          (effective_marks / max_marks) * weightage_percent
                      -----------------------------------------------------
                                  sum of weightage_percent

    effective_marks = 0.0 if (is_absent or is_malpractice) else marks_obtained

Dividing by the *allocated* weightage rather than by 100 means a subject that
has run two of its three components reports an honest percentage of what has
happened so far, instead of appearing to have failed the missing third.

What this module refuses to do, and why:

  * **report a partial SGPA.** If any credit-bearing subject lacks a grade,
    ``has_data`` is False and ``reason`` says what is missing. A partial SGPA
    will be screenshotted and believed;
  * **let a zero stand in for "not computed".** An ungraded subject has no
    letter — not an F, not a 0.0;
  * **count a DRAFT assessment.** Publishing is what makes a mark real;
  * **score a student who was simply skipped.** One pending mark excludes the
    whole subject rather than silently failing them;
  * **withhold a result over attendance.** Shortage is reported as a flag.
    Withholding is an administrative decision with an appeals process behind
    it; a service that enforces it silently produces a support ticket, not a
    policy.
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.assessment import Assessment
from app.models.mark_record import MarkRecord
from app.models.section import Section
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User
from app.schemas.assessment import (
    COUNTED_ASSESSMENT_STATUSES,
    GRADE_SCALE,
    RESULT_ATTENDANCE_FLAG_THRESHOLD,
    grade_for,
)
from app.schemas.result import (
    AssessmentBreakdown,
    GradeBand,
    SectionResultReport,
    SectionResultRow,
    SectionSubjectColumn,
    StudentResult,
    SubjectResult,
    SubjectResultReport,
)
from app.services import assessment_service, marks_service
from app.services.assessment_service import _bad_request, _forbidden, _not_found, _round

ACTIVE_STUDENT_STATUS = "ACTIVE"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _student_name(student: Student | None) -> str | None:
    if not student:
        return None
    return f"{student.first_name} {student.last_name}".strip() or None


# --------------------------------------------------------------------------
# the counted set
# --------------------------------------------------------------------------

def counted_assessments(
    db: Session,
    section_id: int,
    subject_id: int | None = None,
) -> list[Assessment]:
    """Active, published-or-locked assessments. DRAFT is excluded here, once,
    so no caller downstream can accidentally include it."""
    query = (
        db.query(Assessment)
        .options(
            joinedload(Assessment.subject),
            joinedload(Assessment.faculty),
            joinedload(Assessment.section),
        )
        .filter(
            Assessment.section_id == section_id,
            Assessment.is_active.is_(True),
            Assessment.status.in_(COUNTED_ASSESSMENT_STATUSES),
        )
    )
    if subject_id is not None:
        query = query.filter(Assessment.subject_id == subject_id)
    return query.order_by(
        Assessment.subject_id.asc(),
        Assessment.assessment_type.asc(),
        Assessment.sequence_no.asc(),
    ).all()


def _marks_by_assessment(db: Session, assessment_ids: list[int]) -> dict[int, dict[int, MarkRecord]]:
    """assessment_id -> student_id -> record, in one query."""
    if not assessment_ids:
        return {}
    records = (
        db.query(MarkRecord)
        .filter(MarkRecord.assessment_id.in_(set(assessment_ids)))
        .all()
    )
    grouped: dict[int, dict[int, MarkRecord]] = {}
    for record in records:
        grouped.setdefault(record.assessment_id, {})[record.student_id] = record
    return grouped


# --------------------------------------------------------------------------
# one student, one subject
# --------------------------------------------------------------------------

def subject_result(
    student_id: int,
    assessments: list[Assessment],
    marks: dict[int, dict[int, MarkRecord]],
) -> SubjectResult:
    """The weighted percentage, or an honest refusal to compute one."""
    first = assessments[0]
    subject = first.subject

    breakdown: list[AssessmentBreakdown] = []
    allocated = 0.0
    earned = 0.0
    pending = 0

    for assessment in assessments:
        max_marks = float(assessment.max_marks or 0.0)
        weightage = float(assessment.weightage_percent or 0.0)
        pass_mark = marks_service.pass_mark_for(assessment)
        record = marks.get(assessment.id, {}).get(student_id)

        row = AssessmentBreakdown(
            assessment_id=assessment.id,
            name=assessment.name,
            assessment_type=assessment.assessment_type,
            sequence_no=assessment.sequence_no,
            status=assessment.status,
            max_marks=max_marks,
            weightage_percent=weightage,
            pass_marks=pass_mark,
        )

        if record is None:
            # Nobody has said anything about this student for this component.
            # It is not a zero, and it disqualifies the whole subject.
            pending += 1
            breakdown.append(row)
            allocated += weightage
            continue

        effective = marks_service._effective_marks(record)
        row.marks_obtained = (
            float(record.marks_obtained) if record.marks_obtained is not None else None
        )
        row.is_absent = bool(record.is_absent)
        row.is_malpractice = bool(record.is_malpractice)
        row.is_pending = False
        row.is_pass = effective >= pass_mark
        if max_marks:
            row.percent = _round(effective * 100.0 / max_marks)
            row.weighted_contribution = _round(weightage * effective / max_marks)
            earned += weightage * effective / max_marks

        allocated += weightage
        breakdown.append(row)

    result = SubjectResult(
        subject_id=first.subject_id,
        subject_code=subject.subject_code if subject else None,
        subject_name=subject.name if subject else None,
        subject_type=subject.subject_type if subject else None,
        credits=subject.credits if subject else None,
        teaching_assignment_id=first.teaching_assignment_id,
        faculty_id=first.faculty_id,
        faculty_name=assessment_service._faculty_name(first.faculty),
        section_id=first.section_id,
        section_name=first.section.name if first.section else None,
        allocated_weightage=_round(allocated),
        assessments_total=len(assessments),
        assessments_counted=len(assessments) - pending,
        assessments_pending=pending,
        breakdown=breakdown,
    )

    if pending:
        result.reason = (
            f"{pending} of {len(assessments)} component(s) have no mark for this student yet."
        )
        return result

    if allocated <= 0:
        result.reason = "No weightage has been allocated to this subject yet."
        return result

    result.percent = _round(earned * 100.0 / allocated)
    result.grade_letter, result.grade_point = grade_for(result.percent)
    result.is_pass = (result.grade_point or 0.0) > 0.0
    result.has_data = True
    return result


# --------------------------------------------------------------------------
# one student, one semester
# --------------------------------------------------------------------------

def _group_by_subject(assessments: list[Assessment]) -> dict[int, list[Assessment]]:
    grouped: dict[int, list[Assessment]] = {}
    for assessment in assessments:
        grouped.setdefault(assessment.subject_id, []).append(assessment)
    return grouped


def student_result(
    db: Session,
    student: Student,
    include_attendance: bool = True,
) -> StudentResult:
    assessments = counted_assessments(db, student.section_id)
    marks = _marks_by_assessment(db, [item.id for item in assessments])

    subjects = [
        subject_result(student.id, group, marks)
        for group in _group_by_subject(assessments).values()
    ]
    subjects.sort(key=lambda item: (item.subject_code or ""))

    section = student.section
    semester = student.semester
    course = student.course
    department = student.department

    result = StudentResult(
        student_id=student.id,
        student_code=student.student_id,
        student_name=_student_name(student),
        student_status=student.status,
        section_id=student.section_id,
        section_name=section.name if section else None,
        semester_id=student.semester_id,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=student.course_id,
        course_name=course.name if course else None,
        department_id=student.department_id,
        department_name=department.name if department else None,
        subjects=subjects,
        generated_at=_now(),
    )

    complete = [item for item in subjects if item.has_data]
    result.subjects_complete = len(complete)
    result.subjects_pending = len(subjects) - len(complete)
    result.subjects_passed = sum(1 for item in complete if item.is_pass)
    result.subjects_failed = len(complete) - result.subjects_passed
    result.total_credits = sum(item.credits or 0 for item in subjects)
    result.earned_credits = sum(item.credits or 0 for item in complete)

    if include_attendance:
        _attach_attendance(db, student, result)

    if not subjects:
        result.reason = "No published assessments for this section yet."
        return result

    if result.subjects_pending:
        # A partial SGPA is worse than none: it will be screenshotted and
        # believed. Name what is missing instead.
        missing = ", ".join(
            item.subject_code or str(item.subject_id)
            for item in subjects
            if not item.has_data
        )
        result.reason = f"Marks are still incomplete for: {missing}."
        return result

    credits = sum(item.credits or 0 for item in complete)
    if credits <= 0:
        result.reason = "No credit-bearing subject has a grade yet."
        return result

    points = sum((item.grade_point or 0.0) * (item.credits or 0) for item in complete)
    result.sgpa = _round(points / credits)
    result.overall_percent = _round(
        sum((item.percent or 0.0) * (item.credits or 0) for item in complete) / credits
    )
    result.has_data = True
    return result


def _attach_attendance(db: Session, student: Student, result: StudentResult) -> None:
    """Reported beside the result, never used to withhold it."""
    from app.services import attendance_service

    summary = attendance_service.student_summary(db, student)
    if summary.overall_countable <= 0:
        return
    result.attendance_percent = summary.overall_percentage
    result.attendance_short = summary.overall_percentage < RESULT_ATTENDANCE_FLAG_THRESHOLD


# --------------------------------------------------------------------------
# distributions
# --------------------------------------------------------------------------

def _distribution(percents: list[float]) -> list[GradeBand]:
    bands = [
        GradeBand(grade_letter=letter, grade_point=point, min_percent=minimum)
        for minimum, letter, point in GRADE_SCALE
    ]
    by_letter = {band.grade_letter: band for band in bands}

    for percent in percents:
        letter, _ = grade_for(percent)
        if letter and letter in by_letter:
            by_letter[letter].student_count += 1

    total = len(percents)
    if total:
        for band in bands:
            band.percentage = _round(band.student_count * 100.0 / total)
    return bands


# --------------------------------------------------------------------------
# a section in one subject
# --------------------------------------------------------------------------

def subject_report(db: Session, section_id: int, subject_id: int) -> SubjectResultReport:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found")
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise _not_found("Subject not found")

    semester = section.semester
    report = SubjectResultReport(
        subject_id=subject.id,
        subject_code=subject.subject_code,
        subject_name=subject.name,
        subject_type=subject.subject_type,
        credits=subject.credits,
        section_id=section.id,
        section_name=section.name,
        section_code=section.code,
        semester_id=section.semester_id,
        semester_name=semester.name if semester else None,
        generated_at=_now(),
    )

    assessments = counted_assessments(db, section_id, subject_id=subject_id)
    if not assessments:
        report.reason = (
            f"No published assessments for {subject.subject_code} in {section.name} yet."
        )
        return report

    first = assessments[0]
    report.teaching_assignment_id = first.teaching_assignment_id
    report.faculty_id = first.faculty_id
    report.faculty_name = assessment_service._faculty_name(first.faculty)
    report.allocated_weightage = _round(
        sum(float(item.weightage_percent or 0.0) for item in assessments)
    )
    report.assessments_total = len(assessments)

    marks = _marks_by_assessment(db, [item.id for item in assessments])
    roster = _roster(db, section_id)
    report.total_students = len(roster)

    # Kept as (student, outcome) pairs so the topper can be named. A
    # SubjectResult deliberately carries no student id — it is one student's
    # standing, and who that is belongs to the caller that asked.
    graded: list[tuple[Student, SubjectResult]] = []
    for student in roster:
        outcome = subject_result(student.id, assessments, marks)
        if outcome.has_data:
            graded.append((student, outcome))

    report.graded_students = len(graded)
    report.pending_students = max(len(roster) - len(graded), 0)
    report.assessments_counted = len(assessments) if graded else 0
    report.assessments_pending = 0 if graded else len(assessments)

    if not graded:
        report.reason = (
            "No student in this section has a complete set of marks for this subject yet."
        )
        return report

    percents = [outcome.percent or 0.0 for _, outcome in graded]
    report.pass_count = sum(1 for _, outcome in graded if outcome.is_pass)
    report.fail_count = len(graded) - report.pass_count
    report.pass_percentage = _round(report.pass_count * 100.0 / len(graded))
    report.average_percent = _round(sum(percents) / len(percents))
    report.highest_percent = _round(max(percents))
    report.lowest_percent = _round(min(percents))
    report.distribution = _distribution(percents)

    topper, _ = max(graded, key=lambda pair: pair[1].percent or 0.0)
    report.topper_student_id = topper.id
    report.topper_student_name = _student_name(topper)

    report.has_data = True
    return report


def _roster(db: Session, section_id: int) -> list[Student]:
    from app.services import student_service

    return student_service.list_students(
        db, section_id=section_id, student_status=ACTIVE_STUDENT_STATUS
    )


# --------------------------------------------------------------------------
# a whole section
# --------------------------------------------------------------------------

def section_report(db: Session, section_id: int) -> SectionResultReport:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found")

    semester = section.semester
    course = semester.course if semester else None
    department = course.department if course else None

    report = SectionResultReport(
        section_id=section.id,
        section_name=section.name,
        section_code=section.code,
        semester_id=section.semester_id,
        semester_name=semester.name if semester else None,
        semester_number=semester.semester_number if semester else None,
        course_id=course.id if course else None,
        course_name=course.name if course else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        as_of=date.today(),
        generated_at=_now(),
    )

    assessments = counted_assessments(db, section_id)
    if not assessments:
        report.reason = "No published assessments for this section yet."
        return report

    grouped = _group_by_subject(assessments)
    marks = _marks_by_assessment(db, [item.id for item in assessments])
    roster = _roster(db, section_id)
    report.total_students = len(roster)

    for subject_id, group in grouped.items():
        subject = group[0].subject
        report.subjects.append(
            SectionSubjectColumn(
                subject_id=subject_id,
                subject_code=subject.subject_code if subject else None,
                subject_name=subject.name if subject else None,
                credits=subject.credits if subject else None,
                faculty_name=assessment_service._faculty_name(group[0].faculty),
                allocated_weightage=_round(
                    sum(float(item.weightage_percent or 0.0) for item in group)
                ),
            )
        )
    report.subjects.sort(key=lambda column: (column.subject_code or ""))

    sgpas: list[float] = []
    all_percents: list[float] = []

    for student in roster:
        outcomes = [subject_result(student.id, group, marks) for group in grouped.values()]
        complete = [item for item in outcomes if item.has_data]

        row = SectionResultRow(
            student_id=student.id,
            student_code=student.student_id,
            student_name=_student_name(student),
            student_status=student.status,
            subject_percent={item.subject_id: item.percent for item in outcomes},
            subject_grade={item.subject_id: item.grade_letter for item in outcomes},
            total_credits=sum(item.credits or 0 for item in outcomes),
            earned_credits=sum(item.credits or 0 for item in complete),
            subjects_passed=sum(1 for item in complete if item.is_pass),
            subjects_failed=sum(1 for item in complete if not item.is_pass),
            subjects_pending=len(outcomes) - len(complete),
        )

        credits = row.earned_credits
        if not row.subjects_pending and credits > 0:
            points = sum((item.grade_point or 0.0) * (item.credits or 0) for item in complete)
            row.sgpa = _round(points / credits)
            row.overall_percent = _round(
                sum((item.percent or 0.0) * (item.credits or 0) for item in complete) / credits
            )
            row.has_data = True
            sgpas.append(row.sgpa)
            all_percents.append(row.overall_percent)

        report.students.append(row)

    report.students.sort(key=lambda row: (row.student_code or ""))

    report.complete_students = len(sgpas)
    report.pending_students = max(len(roster) - len(sgpas), 0)

    if not sgpas:
        report.reason = "No student in this section has a complete set of marks yet."
        return report

    report.pass_count = sum(
        1 for row in report.students if row.has_data and row.subjects_failed == 0
    )
    report.fail_count = report.complete_students - report.pass_count
    report.pass_percentage = _round(report.pass_count * 100.0 / report.complete_students)
    report.average_sgpa = _round(sum(sgpas) / len(sgpas))
    report.distribution = _distribution(all_percents)
    report.has_data = True
    return report


# --------------------------------------------------------------------------
# access
# --------------------------------------------------------------------------

def result_for_user(db: Session, user: User) -> StudentResult:
    if user.role != "STUDENT":
        raise _bad_request(
            "Only students have a personal result. Use the section or student report instead."
        )
    from app.services import student_service

    student = student_service.get_student_for_user(db, user.id)
    return student_result(db, student)


def get_student_or_404(db: Session, student_id: int) -> Student:
    from app.services import student_service

    return student_service.get_student_or_404(db, student_id)


def ensure_section_in_scope(db: Session, user: User, section: Section) -> None:
    if user.role == "ADMIN":
        return
    faculty = assessment_service.faculty_for_user(db, user)
    semester = section.semester
    course = semester.course if semester else None
    if course and course.department_id != faculty.department_id:
        raise _forbidden("You can only view results from your own department.")
