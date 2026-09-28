from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.academic_year import AcademicYear
from app.models.course import Course
from app.models.semester import Semester
from app.models.user import User
from app.schemas.semester import SemesterCreate, SemesterOut, SemesterUpdate

router = APIRouter()


def _validate_range(start_date: date, end_date: date) -> None:
    if end_date <= start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End date must be after the start date.")


def _normalize_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Semester name cannot be empty.")
    return value


def _serialize_semester(semester: Semester) -> SemesterOut:
    return SemesterOut(
        id=semester.id,
        course_id=semester.course_id,
        academic_year_id=semester.academic_year_id,
        semester_number=semester.semester_number,
        name=semester.name,
        start_date=semester.start_date,
        end_date=semester.end_date,
        is_active=semester.is_active,
        created_at=semester.created_at,
        updated_at=semester.updated_at,
        course_name=semester.course.name if semester.course else None,
        academic_year_name=semester.academic_year.name if semester.academic_year else None,
    )


@router.get("/", response_model=list[SemesterOut])
def list_semesters_root(
    course_id: int | None = Query(default=None, description="Filter by course_id"),
    academic_year_id: int | None = Query(default=None, description="Filter by academic_year_id"),
    search: str | None = Query(default=None, description="Search by semester name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_semesters(course_id=course_id, academic_year_id=academic_year_id, search=search, db=db, current_user=current_user)


@router.post("", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
def create_semester(
    payload: SemesterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    academic_year = db.query(AcademicYear).filter(AcademicYear.id == payload.academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    _validate_range(payload.start_date, payload.end_date)
    name = _normalize_name(payload.name)

    duplicate = (
        db.query(Semester)
        .filter(
            Semester.course_id == payload.course_id,
            Semester.academic_year_id == payload.academic_year_id,
            Semester.semester_number == payload.semester_number,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A semester with the same course, year, and number already exists.")

    semester = Semester(
        course_id=payload.course_id,
        academic_year_id=payload.academic_year_id,
        semester_number=payload.semester_number,
        name=name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return _serialize_semester(semester)


@router.get("", response_model=list[SemesterOut])
def list_semesters(
    course_id: int | None = Query(default=None, description="Filter by course_id"),
    academic_year_id: int | None = Query(default=None, description="Filter by academic_year_id"),
    search: str | None = Query(default=None, description="Search by semester name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    query = db.query(Semester).join(Course, Semester.course_id == Course.id).join(AcademicYear, Semester.academic_year_id == AcademicYear.id)

    if course_id is not None:
        query = query.filter(Semester.course_id == course_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if search:
        query = query.filter(Semester.name.ilike(f"%{search.strip()}%"))

    return [_serialize_semester(item) for item in query.order_by(Semester.start_date.asc(), Semester.id.asc()).all()]


@router.get("/{semester_id}", response_model=SemesterOut)
def get_semester(
    semester_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
    return _serialize_semester(semester)


@router.put("/{semester_id}", response_model=SemesterOut)
def update_semester(
    semester_id: int,
    payload: SemesterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    academic_year = db.query(AcademicYear).filter(AcademicYear.id == payload.academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    _validate_range(payload.start_date, payload.end_date)
    name = _normalize_name(payload.name)

    duplicate = (
        db.query(Semester)
        .filter(
            Semester.id != semester_id,
            Semester.course_id == payload.course_id,
            Semester.academic_year_id == payload.academic_year_id,
            Semester.semester_number == payload.semester_number,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A semester with the same course, year, and number already exists.")

    semester.course_id = payload.course_id
    semester.academic_year_id = payload.academic_year_id
    semester.semester_number = payload.semester_number
    semester.name = name
    semester.start_date = payload.start_date
    semester.end_date = payload.end_date
    semester.is_active = payload.is_active
    db.commit()
    db.refresh(semester)
    return _serialize_semester(semester)


@router.delete("/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester(
    semester_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    semester = db.query(Semester).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

    db.delete(semester)
    db.commit()
    return None
