from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee
from app.schemas.employee import EmployeeResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=list[EmployeeResponse])
def list_employees(db: Session = Depends(get_db)) -> list[Employee]:
    return list(db.scalars(select(Employee).order_by(Employee.employee_code)))


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: uuid.UUID, db: Session = Depends(get_db)) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee
