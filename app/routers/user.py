from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.auth.dependencies import require_admin, get_current_user
from app.database import get_db
from app.models.user import User,RoleEnum
from app.models.department import Department
from app.schemas.user import UserRequest, UserResponse
from app.auth.security import hash_password
import uuid


router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse)
def create_user(user: UserRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    if user.role == RoleEnum.superadmin and current_user.role != RoleEnum.superadmin:
        raise HTTPException(status_code=403, detail="Only a superadmin can create a superadmin")

    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    if user.department_id:
        department = db.query(Department).filter(Department.id == user.department_id).first()
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role,
        start_date=user.start_date,
        department_id=user.department_id,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e.orig))
    db.refresh(new_user)
    return new_user


@router.get("/", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return db.query(User).all()

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

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