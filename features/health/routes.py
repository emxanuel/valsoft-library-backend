from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from database.session import get_session

health_router = APIRouter(tags=["health"])


@health_router.get("/health/live")
def live() -> dict:
    """Liveness: process is running (no database check)."""
    return {"status": "ok"}


@health_router.get("/health/ready")
def ready(session: Session = Depends(get_session)) -> dict:
    """Readiness: application can serve traffic (database reachable)."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unavailable: database unreachable",
        )
    return {"status": "ok", "database": "ok"}
