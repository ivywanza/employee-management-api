
import uuid
from datetime import date, datetime
from pydantic import BaseModel
from app.models.leave import LeaveStatusEnum


class LeaveRequestRequest(BaseModel):
    leave_type: str = "sick"
    start_date: date
    end_date: date
    reason: str | None = None
    emergency_contact_name: str
    emergency_contact_phone: str


class LeaveRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    applicant_name: str | None = None
    department: str | None = None
    leave_type: str
    start_date: date
    end_date: date
    days: int
    reason: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    status: LeaveStatusEnum
    reviewed_by: uuid.UUID | None = None
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
