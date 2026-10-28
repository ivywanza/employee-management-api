
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.department import (
    DepartmentRequest,
    DepartmentResponse,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


def role_name(user: User) -> str:
    return str(getattr(user.role, "value", user.role)).lower()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if role_name(user) not in {"admin", "superadmin"}:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view departments.",
        )
    return user


def require_superadmin(
    user: User = Depends(get_current_user),
) -> User:
    if role_name(user) != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can manage departments.",
        )
    return user


@router.get("/")
def list_departments(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    departments = (
        db.query(Department)
        .order_by(Department.name.asc())
        .all()
    )

    result = []

    for department in departments:
        employee_count = (
            db.query(User)
            .filter(
                User.department_id == department.id,
                User.is_active.is_(True),
            )
            .count()
        )

        result.append({
            "id": department.id,
            "name": department.name,
            "employee_count": employee_count,
        })

    return result


@router.post(
    "/",
    status_code=201,
    response_model=DepartmentResponse,
)
def create_department(
    payload: DepartmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Department name is required.",
        )

    duplicate = (
        db.query(Department)
        .filter(Department.name.ilike(name))
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="A department with this name already exists.",
        )

    department = Department(name=name)
    db.add(department)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A department with this name already exists.",
        )

    db.refresh(department)
    return department


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
)
def update_department(
    department_id: str,
    payload: DepartmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    department = (
        db.query(Department)
        .filter(Department.id == department_id)
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Department not found.",
        )

    name = payload.name.strip()

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Department name is required.",
        )

    duplicate = (
        db.query(Department)
        .filter(
            Department.name.ilike(name),
            Department.id != department.id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="A department with this name already exists.",
        )

    department.name = name

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A department with this name already exists.",
        )

    db.refresh(department)
    return department


@router.delete(
    "/{department_id}",
    status_code=204,
)
def delete_department(
    department_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    department = (
        db.query(Department)
        .filter(Department.id == department_id)
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=404,
            detail="Department not found.",
        )

    linked_users = (
        db.query(User)
        .filter(User.department_id == department.id)
        .count()
    )

    if linked_users:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This department has {linked_users} associated user(s). "
                "Reassign them before deleting it."
            ),
        )

    db.delete(department)
    db.commit()
    return None
