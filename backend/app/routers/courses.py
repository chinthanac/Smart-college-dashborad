from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.course import Course
from app.models.department import Department
from app.models.user import User
from app.schemas.course import CourseCreate, CourseOut, CourseUpdate

router = APIRouter()


@router.get("/", response_model=list[CourseOut])
def list_courses_root(
    department_id: int | None = Query(default=None, description="Filter courses by department_id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_courses(department_id=department_id, db=db, current_user=current_user)


def serialize_course(course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        department_id=course.department_id,
        department_name=course.department.name if course.department else None,
        department_code=course.department.code if course.department else None,
        name=course.name,
        code=course.code,
        degree=course.degree,
        duration_years=course.duration_years,
        description=course.description,
        is_active=course.is_active,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    department = db.query(Department).filter(Department.id == payload.department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    code = payload.code.strip().upper()
    name = payload.name.strip()
    degree = payload.degree.strip()

    if db.query(Course).filter(Course.code == code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course code already exists")

    course = Course(
        department_id=department.id,
        name=name,
        code=code,
        degree=degree,
        duration_years=payload.duration_years,
        description=payload.description.strip() if payload.description else None,
        is_active=True,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return serialize_course(course)


@router.get("", response_model=list[CourseOut])
def list_courses(
    department_id: int | None = Query(default=None, description="Filter courses by department_id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    query = db.query(Course).join(Department, Course.department_id == Department.id)
    if department_id is not None:
        query = query.filter(Course.department_id == department_id)
    return [serialize_course(course) for course in query.order_by(Course.created_at.desc()).all()]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return serialize_course(course)


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    department = db.query(Department).filter(Department.id == payload.department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    new_code = payload.code.strip().upper()
    if new_code != course.code and db.query(Course).filter(Course.code == new_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course code already exists")

    course.department_id = payload.department_id
    course.name = payload.name.strip()
    course.code = new_code
    course.degree = payload.degree.strip()
    course.duration_years = payload.duration_years
    course.description = payload.description.strip() if payload.description else None
    course.is_active = payload.is_active
    db.commit()
    db.refresh(course)
    return serialize_course(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    db.delete(course)
    db.commit()
    return None
