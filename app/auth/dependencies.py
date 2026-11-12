
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, RoleEnum
from app.auth.jwt_handler import decode_access_token


bearer_scheme = HTTPBearer()


# Authenticates the user and verifies that their account is active.
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


# Creates a permission check for specified system roles.
def require_roles(*allowed_roles: RoleEnum):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this")
        return current_user

    return checker


# Admin and Superadmin permissions.
# HR is intentionally excluded from this dependency.
require_admin = require_roles(RoleEnum.admin, RoleEnum.superadmin)


# Administrative permissions shared by Admin, HR and Superadmin.
require_admin_or_hr = require_roles(
    RoleEnum.admin,
    RoleEnum.hr,
    RoleEnum.superadmin,
)


# Permissions for HR-specific operations.
require_hr_or_superadmin = require_roles(
    RoleEnum.hr,
    RoleEnum.superadmin,
)
