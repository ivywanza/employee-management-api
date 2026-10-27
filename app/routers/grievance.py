
import hashlib
import hmac
import os
import secrets
import time
import uuid
from datetime import datetime
from threading import Lock
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models.grievance import (
    Grievance,
    GrievanceCategory,
    GrievanceKind,
    GrievanceStatus,
)
from app.models.user import RoleEnum, User
from app.schemas.grievance import (
    GrievanceCreate,
    GrievanceResponse,
    GrievanceUpdate,
)
from app.ws import manager

router = APIRouter(prefix="/grievances", tags=["Grievances"])

WINDOW_SECONDS = 24 * 60 * 60
MAX_SUBMISSIONS = 3

# Use a stable secret configured in the server environment. The fallback
# keeps local development working, but resets rate-limit identities on restart.
_RATE_LIMIT_SALT = os.getenv(
    "GRIEVANCE_RATE_LIMIT_SALT"
) or secrets.token_hex(32)

_submission_times: dict[str, list[float]] = {}
_rate_limit_lock = Lock()


def enforce_submission_limit(
    current_user: User = Depends(get_current_user),
) -> None:
    """Validate the user and rate-limit without storing their identity."""
    now = time.time()
    user_key = hmac.new(
        _RATE_LIMIT_SALT.encode("utf-8"),
        str(current_user.id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    with _rate_limit_lock:
        # Prune expired entries so the in-memory map does not grow forever.
        for key in list(_submission_times):
            active = [
                stamp
                for stamp in _submission_times[key]
                if now - stamp < WINDOW_SECONDS
            ]
            if active:
                _submission_times[key] = active
            else:
                del _submission_times[key]

        recent = [
            stamp
            for stamp in _submission_times.get(user_key, [])
            if now - stamp < WINDOW_SECONDS
        ]

        if len(recent) >= MAX_SUBMISSIONS:
            raise HTTPException(
                status_code=429,
                detail=(
                    "You have reached the limit of 3 submissions in 24 hours. "
                    "Please try again later."
                ),
            )

        # Count this attempt before processing the request.
        recent.append(now)
        _submission_times[user_key] = recent


def require_superadmin(
    current_user: User = Depends(require_roles(RoleEnum.superadmin)),
) -> User:
    return current_user


@router.post("/")
def submit_grievance(
    data: GrievanceCreate,
    background_tasks: BackgroundTasks,
    _: None = Depends(enforce_submission_limit),
    db: Session = Depends(get_db),
):
    # Do not accept or read current_user in this handler.
    body = data.body.strip()
    if not 10 <= len(body) <= 3000:
        raise HTTPException(
            status_code=422,
            detail="The message must contain 10 to 3000 characters.",
        )

    subject = data.subject.strip() if data.subject else None
    if subject == "":
        subject = None

    created_at = datetime.utcnow().replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    grievance = Grievance(
        kind=data.kind,
        category=data.category,
        subject=subject,
        body=body,
        status=GrievanceStatus.new,
        created_at=created_at,
    )

    db.add(grievance)
    db.commit()

    # Notify only active superadmins. The event has no sender, subject,
    # grievance ID, body or category.
    superadmin_ids = [
        str(user_id)
        for (user_id,) in db.query(User.id).filter(
            User.is_active.is_(True),
            User.role == RoleEnum.superadmin,
        ).all()
    ]

    if superadmin_ids:
        background_tasks.add_task(
            manager.send_to_users,
            superadmin_ids,
            {
                "type": "notification",
                "title": "A new grievance was received",
                "message": "A new grievance was received",
                "target": "/grievances/inbox",
            },
        )

    return {"ok": True}


@router.get("/", response_model=list[GrievanceResponse])
def list_grievances(
    kind: Optional[GrievanceKind] = Query(default=None),
    status: Optional[GrievanceStatus] = Query(default=None),
    category: Optional[GrievanceCategory] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    query = db.query(Grievance)

    if kind is not None:
        query = query.filter(Grievance.kind == kind)
    if status is not None:
        query = query.filter(Grievance.status == status)
    if category is not None:
        query = query.filter(Grievance.category == category)

    return query.order_by(Grievance.created_at.desc(), Grievance.id.desc()).all()


@router.patch("/{grievance_id}", response_model=GrievanceResponse)
def update_grievance(
    grievance_id: uuid.UUID,
    data: GrievanceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    grievance = (
        db.query(Grievance)
        .filter(Grievance.id == grievance_id)
        .first()
    )

    if grievance is None:
        raise HTTPException(status_code=404, detail="Grievance not found")

    grievance.status = data.status
    grievance.admin_note = (
        data.admin_note.strip() if data.admin_note else None
    )
    grievance.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(grievance)
    return grievance
