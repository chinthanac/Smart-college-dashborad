from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.user import User
from app.schemas.stats import DashboardStats
from app.services import stats_service

router = APIRouter()


@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Everything the admin dashboard needs, in one call.

    Admin-only: it reports across every department, which is exactly what a
    department-scoped faculty account must not see.
    """
    return stats_service.dashboard(db)
