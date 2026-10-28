
import hashlib
import os
import secrets
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.asset import Asset, AssetStatus
from app.models.user import User
from app.services.asset_email import send_assignment_email


router = APIRouter(prefix="/assets", tags=["Asset Assignments"])

logger = logging.getLogger(__name__)

class EmployeeOption(BaseModel):
    id: str
    full_name: str
    email: EmailStr


class AssignmentCreate(BaseModel):
    employee_id: str


def require_superadmin(user):
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required.")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.get("/employees/search", response_model=list[EmployeeOption])
def search_employees(
    q: str = "",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_superadmin(current_user)

    term = q.strip()
    if len(term) < 2:
        return []

    employees = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            (
                User.full_name.ilike(f"%{term}%")
                | User.email.ilike(f"%{term}%")
            ),
        )
        .order_by(User.full_name.asc())
        .limit(20)
        .all()
    )

    return [
        EmployeeOption(
            id=str(employee.id),
            full_name=employee.full_name,
            email=employee.email,
        )
        for employee in employees
        if employee.email
    ]


@router.post("/{asset_id}/assign")
def initiate_assignment(
    asset_id: str,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    require_superadmin(current_user)

    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id)
        .with_for_update()
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    if asset.status != AssetStatus.available:
        raise HTTPException(
            status_code=409,
            detail="Only available assets can be assigned.",
        )

    employee = (
        db.query(User)
        .filter(
            User.id == payload.employee_id,
            User.is_active.is_(True),
        )
        .first()
    )
    if not employee or not employee.email:
        raise HTTPException(
            status_code=404,
            detail="Active employee with an email address not found.",
        )

    
    token = secrets.token_urlsafe(32)

    asset.assignment_pending_to_id = employee.id
    asset.assignment_token_hash = hash_token(token)
    asset.assignment_token_expires_at = (
        datetime.utcnow() + timedelta(hours=48)
    )
    asset.status = AssetStatus.pending_assignment

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        send_assignment_email(
            recipient_email=employee.email,
            employee_name=employee.full_name,
            asset_name=asset.name,
            asset_tag=asset.asset_tag,
            token=token,
        )
    except Exception:
        logger.exception(
            "Assignment email failed for asset %s",
            asset.id,
        )
        return {
            "message": (
                "Assignment was recorded, but the notification email "
                "could not be sent. An administrator must retry the notification."
            ),
            "email_sent": False,
            "asset_id": str(asset.id),
        }

    return {
        "message": "Assignment email sent. Waiting for employee acceptance.",
        "email_sent": True,
        "asset_id": str(asset.id),
    }


@router.post("/accept-assignment")
def accept_assignment(
    token: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    asset = (
        db.query(Asset)
        .filter(
            Asset.assignment_token_hash == hash_token(token),
            Asset.status == AssetStatus.pending_assignment,
        )
        .with_for_update()
        .first()
    )

    if not asset:
        raise HTTPException(
            status_code=400,
            detail="Invalid or already-used assignment link.",
        )

    if (
        not asset.assignment_token_expires_at
        or asset.assignment_token_expires_at < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail="Assignment link has expired. Ask an administrator to resend it.",
        )

    if asset.assignment_pending_to_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="This assignment belongs to another employee.",
        )

    asset.assigned_to_id = current_user.id
    asset.status = AssetStatus.assigned
    asset.assigned_at = datetime.utcnow()
    asset.assignment_accepted_at = datetime.utcnow()

    asset.assignment_pending_to_id = None
    asset.assignment_token_hash = None
    asset.assignment_token_expires_at = None

    db.commit()

    return {"message": "Asset assignment accepted successfully."}
