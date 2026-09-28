from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter()


@router.get("/", response_model=list[DepartmentOut])
def list_departments_root(
    search: str | None = Query(default=None, description="Search by department name or code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_departments(search=search, db=db, current_user=current_user)


@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    code = payload.code.strip().upper()
    name = payload.name.strip()
    description = payload.description.strip() if payload.description else None

    if db.query(Department).filter(Department.code == code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department code already exists")

    department = Department(name=name, code=code, description=description, is_active=True)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.get("", response_model=list[DepartmentOut])
def list_departments(
    search: str | None = Query(default=None, description="Search by department name or code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    query = db.query(Department)
    if search:
        term = search.strip().lower()
        query = query.filter(
            (Department.name.ilike(f"%{term}%")) | (Department.code.ilike(f"%{term}%"))
        )
    return query.order_by(Department.created_at.desc()).all()


@router.get("/{department_id}", response_model=DepartmentOut)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


@router.put("/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    new_code = payload.code.strip().upper()
    if new_code != department.code and db.query(Department).filter(Department.code == new_code).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Department code already exists")

    department.name = payload.name.strip()
    department.code = new_code
    department.description = payload.description.strip() if payload.description else None
    department.is_active = payload.is_active
    db.commit()
    db.refresh(department)
    return department


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    db.delete(department)
    db.commit()
    return None
