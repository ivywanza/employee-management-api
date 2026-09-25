import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class LeaveRequestRequest(BaseModel):
    user_id: uuid.UUID
    leave_type: str = "sick"
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveRequestResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    leave_type: str
    start_date: date
    end_date: date
    reason: Optional[str]
    reviewed: bool
    submitted_at: datetime

    class Config:
        from_attributes = True