from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from app.auth.security import verify_password, hash_password
from app.auth.jwt_handler import create_access_token
from app.auth.verification_codes import create_code, check_code
from app.mailer import send_email

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == data.email).first()
    if user and user.is_active:
        code = create_code(user.id, "password_reset")
        background_tasks.add_task(
            send_email,
            user.email,
            "Reset your RedAnt Portal password",
            f"Your password reset code is {code}.\n\n"
            "It expires in 10 minutes. If you didn't ask for this, you can ignore this email.",
        )
    return MessageResponse(message="If that email has an account, a reset code has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not check_code(user.id, "password_reset", data.code):
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return MessageResponse(message="Password updated. You can now sign in.")