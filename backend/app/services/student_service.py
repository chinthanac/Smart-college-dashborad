"""Student CRUD service.

The router stays thin: every business rule lives here — the academic
hierarchy checks, the uniqueness checks, and the paired ``users`` +
``students`` write that must succeed or fail as one unit.
"""

import re
import secrets
import string

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.academic_year import AcademicYear
from app.models.course import Course
from app.models.department import Department
from app.models.section import Section
from app.models.semester import Semester
from app.models.student import Student
from app.models.user import User
from app.schemas.student import (
    GENDERS,
    STATUSES,
    StudentCreate,
    StudentOut,
    StudentProfileUpdate,
    StudentUpdate,
)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")

STUDENT_ROLE = "STUDENT"


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=detail)


# --------------------------------------------------------------------------
# field-level validation
# --------------------------------------------------------------------------

def normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise _bad_request("Please enter a valid email address.")
    return email


def normalize_phone(value: str) -> str:
    phone = re.sub(r"[\s()-]", "", (value or "").strip())
    if not PHONE_PATTERN.match(phone):
        raise _bad_request("Phone number must be 10 to 15 digits, optionally starting with '+'.")
    return phone


def normalize_student_id(value: str) -> str:
    student_id = (value or "").strip().upper()
    if not student_id:
        raise _bad_request("Student ID cannot be empty.")
    return student_id


def normalize_text(value: str, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise _bad_request(f"{label} cannot be empty.")
    return text


def validate_gender(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    gender = value.strip()
    if gender not in GENDERS:
        raise _bad_request(f"Gender must be one of: {', '.join(GENDERS)}.")
    return gender


def validate_status(value: str | None) -> str:
    student_status = (value or "ACTIVE").strip().upper()
    if student_status not in STATUSES:
        raise _bad_request(f"Status must be one of: {', '.join(STATUSES)}.")
    return student_status


def generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(c in "!@#$%" for c in candidate)
        ):
            return candidate


# --------------------------------------------------------------------------
# the academic hierarchy chain
# --------------------------------------------------------------------------

def validate_academic_chain(
    db: Session,
    department_id: int,
    course_id: int,
    academic_year_id: int,
    semester_id: int,
    section_id: int,
) -> tuple[Department, Course, AcademicYear, Semester, Section]:
    """Walk Department → Course → Academic Year → Semester → Section.

    Each level must exist AND belong to the level above it. The API never
    trusts the ids it is handed, so a hand-crafted request cannot place a
    CSE student into an ECE course.
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise _not_found("Department not found")

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise _not_found("Course not found")
    if course.department_id != department.id:
        raise _bad_request("Course does not belong to selected department.")

    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise _not_found("Academic year not found")

    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise _not_found("Semester not found")
    if semester.course_id != course.id:
        raise _bad_request("Semester does not belong to selected course.")
    if semester.academic_year_id != academic_year.id:
        raise _bad_request("Semester does not belong to selected academic year.")

    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise _not_found("Section not found")
    if section.semester_id != semester.id:
        raise _bad_request("Section does not belong to selected semester.")

    return department, course, academic_year, semester, section


# --------------------------------------------------------------------------
# uniqueness
# --------------------------------------------------------------------------

def ensure_unique_student_id(db: Session, student_id: str, exclude_id: int | None = None) -> None:
    query = db.query(Student).filter(Student.student_id.ilike(student_id))
    if exclude_id is not None:
        query = query.filter(Student.id != exclude_id)
    if query.first():
        raise _conflict(f"Student ID '{student_id}' already exists.")


def ensure_unique_email(db: Session, email: str, exclude_user_id: int | None = None) -> None:
    query = db.query(User).filter(User.email == email)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise _conflict(f"Email '{email}' already exists.")


def suggest_student_id(db: Session, department_id: int, academic_year_id: int) -> str:
    """Offer a DEPTCODE + YY + sequence starting point.

    Deliberately only a suggestion the Admin can overwrite — the real
    convention differs per college, so nothing here is enforced.
    """
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise _not_found("Department not found")

    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise _not_found("Academic year not found")

    year_digits = re.sub(r"[^0-9]", "", academic_year.name)[:4]
    year_part = year_digits[-2:] if len(year_digits) >= 2 else str(academic_year.start_date.year)[-2:]
    prefix = f"{department.code.upper()}{year_part}"

    taken = {
        row.student_id
        for row in db.query(Student).filter(Student.student_id.ilike(f"{prefix}%")).all()
    }
    sequence = 1
    while f"{prefix}{sequence:03d}" in taken:
        sequence += 1
    return f"{prefix}{sequence:03d}"


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------

def serialize(student: Student) -> StudentOut:
    return StudentOut(
        id=student.id,
        user_id=student.user_id,
        student_id=student.student_id,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=f"{student.first_name} {student.last_name}".strip(),
        email=student.user.email if student.user else "",
        date_of_birth=student.date_of_birth,
        gender=student.gender,
        phone=student.phone,
        address=student.address,
        department_id=student.department_id,
        course_id=student.course_id,
        academic_year_id=student.academic_year_id,
        semester_id=student.semester_id,
        section_id=student.section_id,
        admission_date=student.admission_date,
        status=student.status,
        created_at=student.created_at,
        updated_at=student.updated_at,
        department_name=student.department.name if student.department else None,
        department_code=student.department.code if student.department else None,
        course_name=student.course.name if student.course else None,
        course_code=student.course.code if student.course else None,
        academic_year_name=student.academic_year.name if student.academic_year else None,
        semester_name=student.semester.name if student.semester else None,
        semester_number=student.semester.semester_number if student.semester else None,
        section_name=student.section.name if student.section else None,
        section_code=student.section.code if student.section else None,
    )


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_students(
    db: Session,
    department_id: int | None = None,
    course_id: int | None = None,
    academic_year_id: int | None = None,
    semester_id: int | None = None,
    section_id: int | None = None,
    student_status: str | None = None,
    search: str | None = None,
) -> list[Student]:
    query = db.query(Student).join(User, Student.user_id == User.id)

    if department_id is not None:
        query = query.filter(Student.department_id == department_id)
    if course_id is not None:
        query = query.filter(Student.course_id == course_id)
    if academic_year_id is not None:
        query = query.filter(Student.academic_year_id == academic_year_id)
    if semester_id is not None:
        query = query.filter(Student.semester_id == semester_id)
    if section_id is not None:
        query = query.filter(Student.section_id == section_id)
    if student_status:
        query = query.filter(Student.status == student_status.strip().upper())
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Student.student_id.ilike(term)
            | Student.first_name.ilike(term)
            | Student.last_name.ilike(term)
            | Student.phone.ilike(term)
            | User.email.ilike(term)
        )

    return query.order_by(Student.student_id.asc(), Student.id.asc()).all()


def get_student_or_404(db: Session, student_pk: int) -> Student:
    student = db.query(Student).filter(Student.id == student_pk).first()
    if not student:
        raise _not_found("Student not found")
    return student


def get_student_for_user(db: Session, user_id: int) -> Student:
    student = db.query(Student).filter(Student.user_id == user_id).first()
    if not student:
        raise _not_found("No student profile is linked to this account.")
    return student


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_student(db: Session, payload: StudentCreate) -> tuple[Student, str | None]:
    """Create the ``users`` row and the ``students`` row as one transaction."""
    student_id = normalize_student_id(payload.student_id)
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone)
    first_name = normalize_text(payload.first_name, "First name")
    last_name = normalize_text(payload.last_name, "Last name")
    gender = validate_gender(payload.gender)
    student_status = validate_status(payload.status)

    validate_academic_chain(
        db,
        payload.department_id,
        payload.course_id,
        payload.academic_year_id,
        payload.semester_id,
        payload.section_id,
    )
    ensure_unique_student_id(db, student_id)
    ensure_unique_email(db, email)

    generated_password = None if payload.password else generate_password()
    raw_password = payload.password or generated_password

    try:
        user = User(
            name=f"{first_name} {last_name}".strip(),
            email=email,
            password_hash=get_password_hash(raw_password),
            role=STUDENT_ROLE,
            is_active=student_status == "ACTIVE",
        )
        db.add(user)
        db.flush()  # assigns user.id without ending the transaction

        student = Student(
            user_id=user.id,
            student_id=student_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=payload.date_of_birth,
            gender=gender,
            phone=phone,
            address=(payload.address or "").strip() or None,
            department_id=payload.department_id,
            course_id=payload.course_id,
            academic_year_id=payload.academic_year_id,
            semester_id=payload.semester_id,
            section_id=payload.section_id,
            admission_date=payload.admission_date,
            status=student_status,
        )
        db.add(student)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the student account. Please try again.")

    db.refresh(student)
    return student, generated_password


def update_student(db: Session, student: Student, payload: StudentUpdate) -> Student:
    student_id = normalize_student_id(payload.student_id)
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone)
    first_name = normalize_text(payload.first_name, "First name")
    last_name = normalize_text(payload.last_name, "Last name")
    gender = validate_gender(payload.gender)
    student_status = validate_status(payload.status)

    validate_academic_chain(
        db,
        payload.department_id,
        payload.course_id,
        payload.academic_year_id,
        payload.semester_id,
        payload.section_id,
    )
    ensure_unique_student_id(db, student_id, exclude_id=student.id)
    ensure_unique_email(db, email, exclude_user_id=student.user_id)

    try:
        student.student_id = student_id
        student.first_name = first_name
        student.last_name = last_name
        student.date_of_birth = payload.date_of_birth
        student.gender = gender
        student.phone = phone
        student.address = (payload.address or "").strip() or None
        student.department_id = payload.department_id
        student.course_id = payload.course_id
        student.academic_year_id = payload.academic_year_id
        student.semester_id = payload.semester_id
        student.section_id = payload.section_id
        student.admission_date = payload.admission_date
        student.status = student_status

        if student.user:
            student.user.email = email
            student.user.name = f"{first_name} {last_name}".strip()
            student.user.is_active = student_status == "ACTIVE"

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the student account. Please try again.")

    db.refresh(student)
    return student


def update_own_profile(db: Session, student: Student, payload: StudentProfileUpdate) -> Student:
    """A student may correct their contact details, nothing academic."""
    student.phone = normalize_phone(payload.phone)
    student.address = (payload.address or "").strip() or None
    db.commit()
    db.refresh(student)
    return student


def set_status(db: Session, student: Student, new_status: str) -> Student:
    student.status = validate_status(new_status)
    if student.user:
        student.user.is_active = student.status == "ACTIVE"
    db.commit()
    db.refresh(student)
    return student


def reset_password(db: Session, student: Student, password: str | None) -> str | None:
    generated_password = None if password else generate_password()
    raw_password = password or generated_password

    if not student.user:
        raise _bad_request("This student record has no linked login account.")

    student.user.password_hash = get_password_hash(raw_password)
    db.commit()
    return generated_password


def delete_student(db: Session, student: Student) -> None:
    """Hard delete, including the login account.

    Prefer set_status(INACTIVE/GRADUATED): once attendance and marks exist,
    deleting a student destroys the history that references them.
    """
    try:
        user = student.user
        db.delete(student)
        if user:
            db.delete(user)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the student account. Please try again.")
