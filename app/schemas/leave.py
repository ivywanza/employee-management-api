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
    approved: bool
    reviewed_by: uuid.UUID
    submitted_at: datetime

    class Config:
        from_attributes = True

class LeaveReviewRequest(BaseModel):
    reviewed_by: uuid.UUID