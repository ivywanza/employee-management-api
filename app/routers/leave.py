import uuid
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leave import LeaveRequest, LeaveStatusEnum
from app.models.user import User
from app.schemas.leave import LeaveRequestRequest, LeaveRequestResponse, LeaveBalanceResponse
from app.auth.dependencies import get_current_user, require_hr_or_superadmin

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])

ANNUAL_ALLOWANCE = 22
MENSTRUAL_MONTHLY_CAP = 2


def days_in(record) -> int:
    return (record.end_date - record.start_date).days + 1


@router.get("/balance", response_model=LeaveBalanceResponse)
def get_leave_balance(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today()
    approved_this_year = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
        .filter(LeaveRequest.status == LeaveStatusEnum.approved)
        .filter(LeaveRequest.start_date >= date(today.year, 1, 1))
        .filter(LeaveRequest.start_date <= date(today.year, 12, 31))
        .all()
    )

    days_used = sum(days_in(r) for r in approved_this_year if r.leave_type != "menstrual")
    menstrual_days_used = sum(
        days_in(r) for r in approved_this_year if r.leave_type == "menstrual" and r.start_date.month == today.month
    )

    return LeaveBalanceResponse(
        year=today.year,
        annual_allowance=ANNUAL_ALLOWANCE,
        days_used=days_used,
        days_remaining=max(0, ANNUAL_ALLOWANCE - days_used),
        menstrual_month=today.strftime("%B"),
        menstrual_days_used=menstrual_days_used,
        menstrual_days_remaining=max(0, MENSTRUAL_MONTHLY_CAP - menstrual_days_used),
    )


@router.post("/", response_model=LeaveRequestResponse)
def submit_leave_request(
    leave: LeaveRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if leave.start_date < date.today():
        raise HTTPException(status_code=400, detail="Start date cannot be in the past")
    if leave.end_date < leave.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before the start date")

    requested_days = (leave.end_date - leave.start_date).days + 1

    approved_existing = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
        .filter(LeaveRequest.status == LeaveStatusEnum.approved)
        .filter(LeaveRequest.start_date >= date(leave.start_date.year, 1, 1))
        .filter(LeaveRequest.start_date <= date(leave.start_date.year, 12, 31))
        .all()
    )

    if leave.leave_type == "menstrual":
        if requested_days > MENSTRUAL_MONTHLY_CAP:
            raise HTTPException(status_code=400, detail=f"Menstrual leave cannot exceed {MENSTRUAL_MONTHLY_CAP} days")
        already = sum(
            days_in(e) for e in approved_existing
            if e.leave_type == "menstrual" and e.start_date.month == leave.start_date.month
        )
        if already + requested_days > MENSTRUAL_MONTHLY_CAP:
            raise HTTPException(
                status_code=400,
                detail=f"Only {MENSTRUAL_MONTHLY_CAP - already} menstrual leave day(s) left this month",
            )
    else:
        days_used = sum(days_in(e) for e in approved_existing if e.leave_type != "menstrual")
        if days_used + requested_days > ANNUAL_ALLOWANCE:
            raise HTTPException(
                status_code=400,
                detail=f"Only {ANNUAL_ALLOWANCE - days_used} leave day(s) remaining this year",
            )

    new_leave = LeaveRequest(
        user_id=current_user.id,
        leave_type=leave.leave_type,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        emergency_contact_name=leave.emergency_contact_name,
        emergency_contact_phone=leave.emergency_contact_phone,
    )
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)
    return new_leave


@router.get("/mine", response_model=list[LeaveRequestResponse])
def my_leave_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
        .order_by(LeaveRequest.submitted_at.desc())
        .all()
    )


@router.get("/", response_model=list[LeaveRequestResponse])
def list_leave_requests(db: Session = Depends(get_db), current_user: User = Depends(require_hr_or_superadmin)):
    return db.query(LeaveRequest).order_by(LeaveRequest.submitted_at.desc()).all()


@router.patch("/{leave_id}/review", response_model=LeaveRequestResponse)
def review_leave_request(
    leave_id: uuid.UUID,
    status: LeaveStatusEnum,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr_or_superadmin),
):
    if status == LeaveStatusEnum.pending:
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    leave.status = status
    leave.reviewed_by = current_user.id
    db.commit()
    db.refresh(leave)
    return leave