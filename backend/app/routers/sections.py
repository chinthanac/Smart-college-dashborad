from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.course import Course
from app.models.section import Section
from app.models.semester import Semester
from app.models.user import User
from app.schemas.section import SectionCreate, SectionOut, SectionUpdate
from app.services import assessment_service, attendance_service, teaching_assignment_service

router = APIRouter()


def _normalize_name(value: str) -> str:
    name = (value or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section name cannot be empty.")
    return name


def _normalize_code(value: str) -> str:
    code = (value or "").strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section code cannot be empty.")
    return code


def _serialize_section(section: Section) -> SectionOut:
    return SectionOut(
        id=section.id,
        semester_id=section.semester_id,
        name=section.name,
        code=section.code,
        capacity=section.capacity,
        room_number=section.room_number,
        is_active=section.is_active,
        created_at=section.created_at,
        updated_at=section.updated_at,
        semester_name=section.semester.name if section.semester else None,
        course_name=section.semester.course.name if section.semester and section.semester.course else None,
        academic_year_name=section.semester.academic_year.name if section.semester and section.semester.academic_year else None,
    )


@router.get("/", response_model=list[SectionOut])
def list_sections_root(
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    return list_sections(semester_id=semester_id, course_id=course_id, academic_year_id=academic_year_id, search=search, db=db, current_user=current_user)


@router.post("", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SectionOut, status_code=status.HTTP_201_CREATED)
def create_section(
    payload: SectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    semester = db.query(Semester).filter(Semester.id == payload.semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

    if payload.capacity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity must be positive.")

    name = _normalize_name(payload.name)
    code = _normalize_code(payload.code)

    duplicate = db.query(Section).filter(Section.semester_id == payload.semester_id, Section.code.ilike(code)).first()
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A section with the same code already exists in this semester.")

    section = Section(
        semester_id=payload.semester_id,
        name=name,
        code=code,
        capacity=payload.capacity,
        room_number=(payload.room_number or "").strip(),
        is_active=payload.is_active,
    )
    if not section.room_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room number cannot be empty.")

    db.add(section)
    db.commit()
    db.refresh(section)
    return _serialize_section(section)


@router.get("", response_model=list[SectionOut])
def list_sections(
    semester_id: int | None = Query(default=None),
    course_id: int | None = Query(default=None),
    academic_year_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    query = db.query(Section).join(Semester, Section.semester_id == Semester.id)

    if semester_id is not None:
        query = query.filter(Section.semester_id == semester_id)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    if course_id is not None:
        # traverse through the semester to the course
        query = query.filter(Semester.course_id == course_id)
    if search:
        term = search.strip()
        query = query.filter((Section.name.ilike(f"%{term}%")) | (Section.code.ilike(f"%{term}%")) | (Section.room_number.ilike(f"%{term}%")))

    return [_serialize_section(item) for item in query.order_by(Section.name.asc(), Section.id.asc()).all()]


@router.get("/{section_id}", response_model=SectionOut)
def get_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return _serialize_section(section)


@router.put("/{section_id}", response_model=SectionOut)
def update_section(
    section_id: int,
    payload: SectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    semester = db.query(Semester).filter(Semester.id == payload.semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

    if payload.capacity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Capacity must be positive.")

    name = _normalize_name(payload.name)
    code = _normalize_code(payload.code)

    duplicate = (
        db.query(Section)
        .filter(Section.id != section_id, Section.semester_id == payload.semester_id, Section.code.ilike(code))
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A section with the same code already exists in this semester.")

    room_number = (payload.room_number or "").strip()
    if not room_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room number cannot be empty.")

    # Moving a section to another semester would strand the subjects it is
    # taught, which is the mismatch teaching assignments exist to prevent.
    if payload.semester_id != section.semester_id and teaching_assignment_service.count_for_section(db, section.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This section has teaching assignments in its current semester. "
                "Remove them before moving it."
            ),
        )

    section.semester_id = payload.semester_id
    section.name = name
    section.code = code
    section.capacity = payload.capacity
    section.room_number = room_number
    section.is_active = payload.is_active
    db.commit()
    db.refresh(section)
    return _serialize_section(section)


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_section(
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    marked = attendance_service.count_for_section(db, section.id)
    if marked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This section has {marked} attendance session(s) on record. "
                "Deactivate it instead — deleting it would destroy that register."
            ),
        )

    assessed = assessment_service.count_for_section(db, section.id)
    if assessed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This section has {assessed} assessment(s) on record. "
                "Deactivate it instead — deleting it would destroy those marks."
            ),
        )

    assigned = teaching_assignment_service.count_for_section(db, section.id)
    if assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This section has {assigned} teaching assignment(s). "
                "Remove them before deleting it, or deactivate the section instead."
            ),
        )

    db.delete(section)
    db.commit()
    return None
