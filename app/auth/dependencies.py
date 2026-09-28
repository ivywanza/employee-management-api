import uuid
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, RoleEnum
from app.auth.jwt_handler import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    error = HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise error

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise error
    return user


def require_roles(*allowed_roles: RoleEnum):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this")
        return current_user
    return checker


require_admin = require_roles(RoleEnum.admin, RoleEnum.superadmin)


def require_hr_or_superadmin(current_user: User = Depends(get_current_user)) -> User:
    is_hr = (
        current_user.department is not None
        and current_user.department.name.strip().lower() == "hr"
    )
    if current_user.role == RoleEnum.superadmin or is_hr:
        return current_user
    raise HTTPException(status_code=403, detail="Only HR or a superadmin can do this")