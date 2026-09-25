import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum


class UserRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.employee
    department_id: Optional[uuid.UUID] = None
    start_date: str

class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: RoleEnum
    department_id: Optional[uuid.UUID]
    start_date: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True