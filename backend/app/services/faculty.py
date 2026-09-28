"""Faculty CRUD service.

Keeps every faculty rule in one place: validation, the paired
``users`` + ``faculty`` write, and the queries the router exposes.
"""

import re
import secrets
import string

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.user import User
from app.schemas.faculty import (
    DESIGNATIONS,
    EMPLOYEE_TYPES,
    FacultyCreate,
    FacultyOut,
    FacultyProfileUpdate,
    FacultyUpdate,
)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PHONE_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")

FACULTY_ROLE = "FACULTY"


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


# --------------------------------------------------------------------------
# validation helpers
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


def normalize_faculty_id(value: str) -> str:
    faculty_id = (value or "").strip().upper()
    if not faculty_id:
        raise _bad_request("Faculty ID cannot be empty.")
    return faculty_id


def normalize_text(value: str, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise _bad_request(f"{label} cannot be empty.")
    return text


def validate_designation(value: str) -> str:
    designation = (value or "").strip()
    if designation not in DESIGNATIONS:
        raise _bad_request(f"Designation must be one of: {', '.join(DESIGNATIONS)}.")
    return designation


def validate_employee_type(value: str) -> str:
    employee_type = (value or "").strip()
    if employee_type not in EMPLOYEE_TYPES:
        raise _bad_request(f"Employee type must be one of: {', '.join(EMPLOYEE_TYPES)}.")
    return employee_type


def get_department_or_404(db: Session, department_id: int) -> Department:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise _not_found("Department not found")
    return department


def ensure_unique_faculty_id(db: Session, faculty_id: str, exclude_id: int | None = None) -> None:
    query = db.query(Faculty).filter(Faculty.faculty_id.ilike(faculty_id))
    if exclude_id is not None:
        query = query.filter(Faculty.id != exclude_id)
    if query.first():
        raise _bad_request(f"Faculty ID '{faculty_id}' is already in use.")


def ensure_unique_email(db: Session, email: str, exclude_user_id: int | None = None) -> None:
    query = db.query(User).filter(User.email == email)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise _bad_request(f"Email '{email}' is already registered.")


def generate_password(length: int = 12) -> str:
    """Readable but random: guarantees one of each class, avoids look-alikes."""
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
# serialization
# --------------------------------------------------------------------------

def serialize(faculty: Faculty) -> FacultyOut:
    return FacultyOut(
        id=faculty.id,
        user_id=faculty.user_id,
        faculty_id=faculty.faculty_id,
        department_id=faculty.department_id,
        first_name=faculty.first_name,
        last_name=faculty.last_name,
        full_name=f"{faculty.first_name} {faculty.last_name}".strip(),
        email=faculty.user.email if faculty.user else "",
        phone=faculty.phone,
        designation=faculty.designation,
        qualification=faculty.qualification,
        joining_date=faculty.joining_date,
        employee_type=faculty.employee_type,
        is_active=faculty.is_active,
        created_at=faculty.created_at,
        updated_at=faculty.updated_at,
        department_name=faculty.department.name if faculty.department else None,
        department_code=faculty.department.code if faculty.department else None,
    )


# --------------------------------------------------------------------------
# queries
# --------------------------------------------------------------------------

def list_faculty(
    db: Session,
    department_id: int | None = None,
    designation: str | None = None,
    employee_type: str | None = None,
    is_active: bool | None = None,
    search: str | None = None,
) -> list[Faculty]:
    query = db.query(Faculty).join(User, Faculty.user_id == User.id)

    if department_id is not None:
        query = query.filter(Faculty.department_id == department_id)
    if designation:
        query = query.filter(Faculty.designation == designation)
    if employee_type:
        query = query.filter(Faculty.employee_type == employee_type)
    if is_active is not None:
        query = query.filter(Faculty.is_active == is_active)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Faculty.faculty_id.ilike(term)
            | Faculty.first_name.ilike(term)
            | Faculty.last_name.ilike(term)
            | Faculty.phone.ilike(term)
            | Faculty.designation.ilike(term)
            | Faculty.qualification.ilike(term)
            | User.email.ilike(term)
        )

    return query.order_by(Faculty.faculty_id.asc(), Faculty.id.asc()).all()


def get_faculty_or_404(db: Session, faculty_pk: int) -> Faculty:
    faculty = db.query(Faculty).filter(Faculty.id == faculty_pk).first()
    if not faculty:
        raise _not_found("Faculty not found")
    return faculty


def get_faculty_for_user(db: Session, user_id: int) -> Faculty:
    faculty = db.query(Faculty).filter(Faculty.user_id == user_id).first()
    if not faculty:
        raise _not_found("No faculty profile is linked to this account.")
    return faculty


# --------------------------------------------------------------------------
# writes
# --------------------------------------------------------------------------

def create_faculty(db: Session, payload: FacultyCreate) -> tuple[Faculty, str | None]:
    """Create the ``users`` row and the ``faculty`` row as one transaction.

    Returns the faculty plus the generated password when one was issued, so
    the Admin can hand the credentials over exactly once.
    """
    faculty_id = normalize_faculty_id(payload.faculty_id)
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone)
    designation = validate_designation(payload.designation)
    employee_type = validate_employee_type(payload.employee_type)
    first_name = normalize_text(payload.first_name, "First name")
    last_name = normalize_text(payload.last_name, "Last name")
    qualification = normalize_text(payload.qualification, "Qualification")

    get_department_or_404(db, payload.department_id)
    ensure_unique_faculty_id(db, faculty_id)
    ensure_unique_email(db, email)

    generated_password = None if payload.password else generate_password()
    raw_password = payload.password or generated_password

    try:
        user = User(
            name=f"{first_name} {last_name}".strip(),
            email=email,
            password_hash=get_password_hash(raw_password),
            role=FACULTY_ROLE,
            is_active=payload.is_active,
        )
        db.add(user)
        db.flush()  # assigns user.id without ending the transaction

        faculty = Faculty(
            user_id=user.id,
            faculty_id=faculty_id,
            department_id=payload.department_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            designation=designation,
            qualification=qualification,
            joining_date=payload.joining_date,
            employee_type=employee_type,
            is_active=payload.is_active,
        )
        db.add(faculty)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not create the faculty account. Please try again.")

    db.refresh(faculty)
    return faculty, generated_password


def update_faculty(db: Session, faculty: Faculty, payload: FacultyUpdate) -> Faculty:
    faculty_id = normalize_faculty_id(payload.faculty_id)
    email = normalize_email(payload.email)
    phone = normalize_phone(payload.phone)
    designation = validate_designation(payload.designation)
    employee_type = validate_employee_type(payload.employee_type)
    first_name = normalize_text(payload.first_name, "First name")
    last_name = normalize_text(payload.last_name, "Last name")
    qualification = normalize_text(payload.qualification, "Qualification")

    get_department_or_404(db, payload.department_id)
    ensure_unique_faculty_id(db, faculty_id, exclude_id=faculty.id)
    ensure_unique_email(db, email, exclude_user_id=faculty.user_id)

    try:
        faculty.faculty_id = faculty_id
        faculty.department_id = payload.department_id
        faculty.first_name = first_name
        faculty.last_name = last_name
        faculty.phone = phone
        faculty.designation = designation
        faculty.qualification = qualification
        faculty.joining_date = payload.joining_date
        faculty.employee_type = employee_type
        faculty.is_active = payload.is_active

        if faculty.user:
            faculty.user.email = email
            faculty.user.name = f"{first_name} {last_name}".strip()
            # a deactivated faculty member must lose login access too
            faculty.user.is_active = payload.is_active

        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not update the faculty account. Please try again.")

    db.refresh(faculty)
    return faculty


def update_own_profile(db: Session, faculty: Faculty, payload: FacultyProfileUpdate) -> Faculty:
    """A faculty member may edit their contact details, nothing structural."""
    first_name = normalize_text(payload.first_name, "First name")
    last_name = normalize_text(payload.last_name, "Last name")

    faculty.first_name = first_name
    faculty.last_name = last_name
    faculty.phone = normalize_phone(payload.phone)
    faculty.qualification = normalize_text(payload.qualification, "Qualification")
    if faculty.user:
        faculty.user.name = f"{first_name} {last_name}".strip()

    db.commit()
    db.refresh(faculty)
    return faculty


def set_status(db: Session, faculty: Faculty, is_active: bool) -> Faculty:
    faculty.is_active = is_active
    if faculty.user:
        faculty.user.is_active = is_active
    db.commit()
    db.refresh(faculty)
    return faculty


def reset_password(db: Session, faculty: Faculty, password: str | None) -> str | None:
    generated_password = None if password else generate_password()
    raw_password = password or generated_password

    if not faculty.user:
        raise _bad_request("This faculty record has no linked login account.")

    faculty.user.password_hash = get_password_hash(raw_password)
    db.commit()
    return generated_password


def delete_faculty(db: Session, faculty: Faculty) -> None:
    """Removes the faculty row and its login account together."""
    from app.services import teaching_assignment_service

    assigned = teaching_assignment_service.count_for_faculty(db, faculty.id)
    if assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This faculty member has {assigned} teaching assignment(s). "
                "Reassign or remove them before deleting the account, "
                "or deactivate the faculty member instead."
            ),
        )

    try:
        user = faculty.user
        db.delete(faculty)
        if user:
            db.delete(user)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise _bad_request("Could not delete the faculty account. Please try again.")
