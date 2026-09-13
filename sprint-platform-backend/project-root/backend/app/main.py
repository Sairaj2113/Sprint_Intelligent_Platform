from fastapi import FastAPI

from app.core.config import settings
from app.routers import (
    contributions,
    documents,
    employees,
    health,
    issues,
    kpis,
    projects,
    sprints,
    workflow,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
    "Backend API for the Sprint Intelligence Platform. "
    "Provides read-only access to employees, projects, sprints, issues, "
    "issue history, testing evidence, deployments, and comments."
),
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(employees.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(sprints.router)
app.include_router(issues.router)
app.include_router(kpis.router)
app.include_router(contributions.router)
app.include_router(workflow.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": settings.PROJECT_NAME,
        "status": "running",
        "docs": "/docs",
    }
