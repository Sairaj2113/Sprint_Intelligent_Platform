from fastapi import FastAPI

from app.core.config import settings
from app.routers import health

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Backend foundation for a Jira-like Sprint Management Platform. "
        "This step only provides database models, connectivity and health "
        "checks — no business logic, frontend, or AI features yet."
    ),
    version="0.1.0",
)

app.include_router(health.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": settings.PROJECT_NAME,
        "status": "running",
        "docs": "/docs",
    }
