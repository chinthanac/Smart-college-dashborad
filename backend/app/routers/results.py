from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_staff_user, get_current_user
from app.models.section import Section
from app.models.user import User
from app.schemas.result import SectionResultReport, StudentResult, SubjectResultReport
from app.services import assessment_service, results_service

router = APIRouter()


def _section_or_404(db: Session, section_id: int) -> Section:
    section = db.query(Section).filter(Section.id == section_id).first()
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Section not found"
        )
    return section


@router.get("/me", response_model=StudentResult)
def get_my_result(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A student's own result. Published components only, and never a partial
    SGPA. Staff get a 400 pointing at the reports."""
    return results_service.result_for_user(db, current_user)


@router.get("/student", response_model=StudentResult)
def get_student_result(
    student_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    student = results_service.get_student_or_404(db, student_id)

    if current_user.role != "ADMIN":
        faculty = assessment_service.faculty_for_user(db, current_user)
        if student.department_id != faculty.department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view results from your own department.",
            )

    return results_service.student_result(db, student)


@router.get("/subject", response_model=SubjectResultReport)
def get_subject_report(
    section_id: int = Query(..., gt=0),
    subject_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """A section's standing in one subject: distribution, pass rate, topper."""
    section = _section_or_404(db, section_id)
    results_service.ensure_section_in_scope(db, current_user, section)
    return results_service.subject_report(db, section_id, subject_id)


@router.get("/section", response_model=SectionResultReport)
def get_section_report(
    section_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """The full mark sheet: every student against every subject."""
    section = _section_or_404(db, section_id)
    results_service.ensure_section_in_scope(db, current_user, section)
    return results_service.section_report(db, section_id)
