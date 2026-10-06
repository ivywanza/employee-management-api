import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel
from app.models.leave import LeaveStatusEnum


class LeaveRequestRequest(BaseModel):
    leave_type: str = "sick"
    start_date: date
    end_date: date
    reason: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class LeaveRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str]
    emergency_contact_name: Optional[str]
    emergency_contact_phone: Optional[str]
    status: LeaveStatusEnum
    reviewed_by: Optional[uuid.UUID] = None
    submitted_at: datetime

    class Config:
        from_attributes = True


class LeaveBalanceResponse(BaseModel):
    year: int
    annual_allowance: int
    days_used: int
    days_remaining: int
    menstrual_month: str
    menstrual_days_used: int
    menstrual_days_remaining: int