
import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.user import RoleEnum


OrganisationType = Literal["red_ant", "bella_organics", "juakali"]


class UserRequest(BaseModel):
    full_name: str
    email: EmailStr
    role: RoleEnum = RoleEnum.employee
    organisation: OrganisationType = "red_ant"
    department_id: Optional[uuid.UUID] = None
    start_date: date


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    organisation: Optional[OrganisationType] = None
    department_id: Optional[uuid.UUID] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: RoleEnum
    organisation: OrganisationType
    department_id: Optional[uuid.UUID] = None
    start_date: date
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreatedResponse(UserResponse):
    email_sent: bool = False


class MeResponse(UserResponse):
    must_change_password: bool
    welcome_shown: bool
    missing_documents: list[str] = Field(default_factory=list)
    needs_wizard: bool = False


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=72)
