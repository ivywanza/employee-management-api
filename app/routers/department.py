from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.department import Department
from app.models.user import User
from app.schemas.department import DepartmentRequest, DepartmentResponse

router = APIRouter(prefix="/departments", tags=["Departments"])

VALID_ORGANISATIONS = {"red_ant", "bella_organics", "juakali"}


def role_name(user: User) -> str:
    return str(getattr(user.role, "value", user.role)).lower()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if role_name(user) not in {"admin", "hr", "superadmin"}:
        raise HTTPException(status_code=403, detail="You do not have permission.")
    return user


def require_superadmin(user: User = Depends(get_current_user)) -> User:
    if role_name(user) != "superadmin":
        raise HTTPException(status_code=403, detail="Only a superadmin can manage departments.")
    return user


@router.get("/")
def list_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(Department)

    # Super Admin can see departments belonging to every organisation.
    if role_name(current_user) != "superadmin":
        query = query.filter(
            Department.organisation == current_user.organisation
        )

    departments = query.order_by(
        Department.organisation.asc(),
        Department.name.asc(),
    ).all()

    return [
        {
            "id": department.id,
            "name": department.name,
            "organisation": department.organisation,
            "employee_count": db.query(User).filter(
                User.department_id == department.id,
                User.is_active.is_(True),
            ).count(),
        }
        for department in departments
    ]


@router.get("/by-organisation/{organisation}")
def departments_by_organisation(
    organisation: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if organisation not in VALID_ORGANISATIONS:
        raise HTTPException(status_code=400, detail="Invalid organisation.")

    # Admin and HR can only access their own organisation's departments.
    if (
        role_name(current_user) != "superadmin"
        and current_user.organisation != organisation
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    return db.query(Department).filter(
        Department.organisation == organisation
    ).order_by(Department.name.asc()).all()


@router.get("/mine")
def get_my_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.department_id:
        return {"id": None, "name": None}

    department = db.query(Department).filter(
        Department.id == current_user.department_id
    ).first()

    if not department:
        return {"id": None, "name": None}

    return {"id": department.id, "name": department.name}


@router.post("/", status_code=201, response_model=DepartmentResponse)
def create_department(
    payload: DepartmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    name = payload.name.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Department name is required.")

    duplicate = db.query(Department).filter(
        Department.name.ilike(name),
        Department.organisation == payload.organisation,
    ).first()

    if duplicate:
        raise HTTPException(status_code=409, detail="This department already exists in that organisation.")

    department = Department(
        name=name,
        organisation=payload.organisation,
    )

    db.add(department)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Department already exists.")

    db.refresh(department)
    return department


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: str,
    payload: DepartmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found.")

    name = payload.name.strip()

    duplicate = db.query(Department).filter(
        Department.name.ilike(name),
        Department.organisation == payload.organisation,
        Department.id != department.id,
    ).first()

    if duplicate:
        raise HTTPException(status_code=409, detail="Department already exists in that organisation.")

    department.name = name
    department.organisation = payload.organisation

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not update department.")

    db.refresh(department)
    return department


@router.delete("/{department_id}", status_code=204)
def delete_department(
    department_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()

    if not department:
        raise HTTPException(status_code=404, detail="Department not found.")

    if db.query(User).filter(User.department_id == department.id).count():
        raise HTTPException(
            status_code=409,
            detail="Reassign employees before deleting this department.",
        )

    db.delete(department)
    db.commit()