from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Sprint
from app.schemas.sprint import SprintResponse

router = APIRouter(prefix="/sprints", tags=["Sprints"])


@router.get("/{sprint_id}", response_model=SprintResponse)
def get_sprint(sprint_id: uuid.UUID, db: Session = Depends(get_db)) -> Sprint:
    sprint = db.get(Sprint, sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint
