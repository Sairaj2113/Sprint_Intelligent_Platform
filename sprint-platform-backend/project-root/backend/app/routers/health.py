from fastapi import APIRouter, HTTPException

from app.database import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Basic liveness check — does not touch the database."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict:
    """Readiness check — verifies the database is reachable."""
    try:
        check_db_connection()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {exc}",
        ) from exc
    return {"status": "ok", "database": "connected"}
