import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leave import LeaveRequest
from app.models.user import User
from app.schemas.leave import LeaveRequestRequest, LeaveRequestResponse, LeaveReviewRequest

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])


@router.post("/", response_model=LeaveRequestResponse)
def submit_leave_request(leave: LeaveRequestRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == leave.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_leave = LeaveRequest(
        user_id=leave.user_id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
    )
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)
    return new_leave


@router.get("/", response_model=list[LeaveRequestResponse])
def list_leave_requests(db: Session = Depends(get_db)):
    return db.query(LeaveRequest).all()


@router.patch("/{leave_id}/review", response_model=LeaveRequestResponse)
def mark_leave_reviewed(leave_id: uuid.UUID, review: LeaveReviewRequest, db: Session = Depends(get_db)):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    reviewer = db.query(User).filter(User.id == review.reviewed_by).first()
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    leave.reviewed = True
    leave.reviewed_by = review.reviewed_by
    db.commit()
    db.refresh(leave)
    return leave