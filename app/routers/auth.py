from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.auth.security import verify_password
from app.auth.jwt_handler import create_access_token

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