from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_faculty_user, get_current_staff_user
from app.models.user import User
from app.schemas.marks import MarkSheet, MarkSheetSave, PendingAssessmentOut
from app.services import marks_service

router = APIRouter()


# --------------------------------------------------------------------------
# static paths only — a mark record is never addressed by its own id, because
# the sheet is the unit of work
# --------------------------------------------------------------------------

@router.get("/my-assessments", response_model=list[PendingAssessmentOut])
def list_my_assessments(
    semester_id: int | None = Query(default=None),
    section_id: int | None = Query(default=None),
    only_pending: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_faculty_user),
):
    """What the signed-in lecturer still has to enter, with progress.

    Outstanding work sorts first. The faculty id comes from the token, never a
    query parameter.
    """
    return marks_service.list_pending_for_faculty(
        db,
        current_user,
        semester_id=semester_id,
        section_id=section_id,
        only_pending=only_pending,
    )


@router.get("/sheet", response_model=MarkSheet)
def get_mark_sheet(
    assessment_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Read-only. Opening a sheet never writes anything.

    Students on the roster with nothing saved come back as PENDING rows with
    every derived field null — never as zeros.
    """
    return marks_service.build_sheet(db, current_user, assessment_id)


@router.post("/sheet", response_model=MarkSheet, status_code=status.HTTP_200_OK)
def save_mark_sheet(
    payload: MarkSheetSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_staff_user),
):
    """Create or correct the marks on one assessment.

    200 rather than 201: saving the same sheet again corrects it in place, so
    the call is idempotent from the caller's point of view. Entries that are
    omitted are left untouched; an entry with no mark and no flag clears the
    student back to pending.
    """
    assessment = marks_service.save_sheet(db, current_user, payload)
    return marks_service.build_sheet(db, current_user, assessment.id)
