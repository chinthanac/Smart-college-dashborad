from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.academic_year import AcademicYear
from app.models.semester import Semester
from app.models.user import User
from app.schemas.academic_year import AcademicYearCreate, AcademicYearOut, AcademicYearUpdate

router = APIRouter()


def _validate_range(start_date: date, end_date: date) -> None:
    if end_date <= start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after the start date.",
        )


def _normalize_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Academic year name cannot be empty.",
        )
    return value


@router.get("/", response_model=list[AcademicYearOut])
def list_academic_years_root(
    search: str | None = Query(default=None, description="Search by academic year name"),
    course_id: int | None = Query(default=None, description="Only years that have semesters for this course"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_academic_years(search=search, course_id=course_id, db=db, current_user=current_user)


@router.post("", response_model=AcademicYearOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AcademicYearOut, status_code=status.HTTP_201_CREATED)
def create_academic_year(
    payload: AcademicYearCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    name = _normalize_name(payload.name)
    _validate_range(payload.start_date, payload.end_date)

    existing = db.query(AcademicYear).filter(AcademicYear.name.ilike(name)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Academic year already exists.",
        )

    if payload.is_current:
        db.query(AcademicYear).filter(AcademicYear.is_current.is_(True)).update({AcademicYear.is_current: False})

    academic_year = AcademicYear(
        name=name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_current=payload.is_current,
        is_active=True,
    )
    db.add(academic_year)
    db.commit()
    db.refresh(academic_year)
    return academic_year


@router.get("", response_model=list[AcademicYearOut])
def list_academic_years(
    search: str | None = Query(default=None, description="Search by academic year name"),
    course_id: int | None = Query(default=None, description="Only years that have semesters for this course"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    query = db.query(AcademicYear)
    if search:
        term = search.strip().lower()
        query = query.filter(AcademicYear.name.ilike(f"%{term}%"))
    if course_id is not None:
        # keeps the dependent dropdowns honest: a year is only offered when
        # the chosen course actually has semesters in it
        query = query.filter(
            AcademicYear.id.in_(
                db.query(Semester.academic_year_id).filter(Semester.course_id == course_id)
            )
        )
    return query.order_by(AcademicYear.start_date.desc(), AcademicYear.id.desc()).all()


@router.get("/{academic_year_id}", response_model=AcademicYearOut)
def get_academic_year(
    academic_year_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")
    return academic_year


@router.put("/{academic_year_id}", response_model=AcademicYearOut)
def update_academic_year(
    academic_year_id: int,
    payload: AcademicYearUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    name = _normalize_name(payload.name)
    _validate_range(payload.start_date, payload.end_date)

    duplicate = db.query(AcademicYear).filter(AcademicYear.name.ilike(name), AcademicYear.id != academic_year_id).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Academic year already exists.")

    if payload.is_current:
        db.query(AcademicYear).filter(AcademicYear.id != academic_year_id, AcademicYear.is_current.is_(True)).update({AcademicYear.is_current: False})

    academic_year.name = name
    academic_year.start_date = payload.start_date
    academic_year.end_date = payload.end_date
    academic_year.is_current = payload.is_current
    academic_year.is_active = payload.is_active
    db.commit()
    db.refresh(academic_year)
    return academic_year


@router.patch("/{academic_year_id}/set-current", response_model=AcademicYearOut)
def set_current_academic_year(
    academic_year_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    db.query(AcademicYear).filter(AcademicYear.id != academic_year_id, AcademicYear.is_current.is_(True)).update({AcademicYear.is_current: False})
    academic_year.is_current = True
    academic_year.is_active = True
    db.commit()
    db.refresh(academic_year)
    return academic_year


@router.delete("/{academic_year_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_academic_year(
    academic_year_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    academic_year = db.query(AcademicYear).filter(AcademicYear.id == academic_year_id).first()
    if not academic_year:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic year not found")

    db.delete(academic_year)
    db.commit()
    return None
