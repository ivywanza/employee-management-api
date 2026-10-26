import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.security import generate_temp_password, hash_password, verify_password
from app.constants import REQUIRED_ONBOARDING_DOCUMENTS
from app.database import get_db
from app.mailer import send_welcome_email
from app.models.department import Department
from app.models.onboarding import OnboardingDocument
from app.models.user import RoleEnum, User
from app.schemas.user import (
    ChangePasswordRequest,
    MeResponse,
    UserCreatedResponse,
    UserRequest,
    UserResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["Users"])


def deliver_welcome(user: User, temp_password: str) -> bool:
    try:
        send_welcome_email(user.email, user.full_name, temp_password)
        return True
    except Exception:
        logger.exception("Could not send the welcome email to %s", user.email)
        return False


def missing_documents(db: Session, user_id) -> list[str]:
    rows = db.query(OnboardingDocument.document_type).filter(OnboardingDocument.user_id == user_id).all()
    uploaded = {row[0] for row in rows}
    return [doc for doc in REQUIRED_ONBOARDING_DOCUMENTS if doc not in uploaded]


@router.post("/", response_model=UserCreatedResponse)
def create_user(
    user: UserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(status_code=403, detail="Only a superadmin can create a superadmin")

    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    if user.department_id and not db.query(Department).filter(Department.id == user.department_id).first():
        raise HTTPException(status_code=404, detail="Department not found")

    temp_password = generate_temp_password()
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(temp_password),  # only the hash is stored
        role=user.role,
        department_id=user.department_id,
        start_date=user.start_date,
        must_change_password=True,
        onboarding_required=True,
        welcome_shown=False,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e.orig))
    db.refresh(new_user)

    result = UserCreatedResponse.model_validate(new_user)
    result.email_sent = deliver_welcome(new_user, temp_password)
    return result


@router.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(User).all()


@router.get("/me", response_model=MeResponse)
def get_me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    missing = missing_documents(db, current_user.id)
    result = MeResponse.model_validate(current_user)
    result.missing_documents = missing
    result.needs_wizard = current_user.must_change_password or (current_user.onboarding_required and bool(missing))
    return result


@router.post("/me/password")
def set_own_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.must_change_password:
        raise HTTPException(status_code=400, detail="Use Forgot Password to change your password")
    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Choose a different password from the temporary one")

    current_user.hashed_password = hash_password(data.new_password)
    current_user.must_change_password = False
    db.commit()
    return {"message": "Password updated"}


@router.post("/me/welcome-seen")
def mark_welcome_seen(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.welcome_shown = True
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/resend-welcome")
def resend_welcome(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't reset your own password this way")
    if target.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(status_code=403, detail="Only a superadmin can do this for a superadmin")

    temp_password = generate_temp_password()
    target.hashed_password = hash_password(temp_password)
    target.must_change_password = True
    db.commit()
    return {"email_sent": deliver_welcome(target, temp_password)}


@router.patch("/{user_id}/status", response_model=UserResponse)
def set_user_active_status(
    user_id: uuid.UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't deactivate your own account")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(status_code=403, detail="Only a superadmin can deactivate a superadmin")

    target.is_active = is_active
    db.commit()
    db.refresh(target)
    return target