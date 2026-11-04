
import uuid
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leave import LeaveRequest, LeaveStatusEnum
from app.models.user import User, RoleEnum
from app.schemas.leave import (
    LeaveRequestRequest,
    LeaveRequestResponse,
    LeaveBalanceResponse,
)
from app.auth.dependencies import (
    get_current_user,
    require_hr_or_superadmin,
)

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])

ANNUAL_ALLOWANCE = 22
MENSTRUAL_MONTHLY_CAP = 2
MAX_EMPLOYEES_PER_DAY = 5

ACTIVE_STATUSES = [
    LeaveStatusEnum.pending,
    LeaveStatusEnum.under_review,
    LeaveStatusEnum.approved,
]


def days_in(record):
    return (record.end_date - record.start_date).days + 1


def is_hr(user):
    return (
        user.department is not None
        and user.department.name.strip().lower() == "hr"
    )


def normalize_kenyan_phone(phone: str) -> str:
    cleaned = re.sub(r"[\s()-]", "", phone)

    # Accept 07XXXXXXXX, 01XXXXXXXX,
    # +2547XXXXXXXX and +2541XXXXXXXX.
    if not re.fullmatch(r"(?:07|01)\d{8}|(?:\+254)(?:7|1)\d{8}", cleaned):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid Kenyan mobile number, e.g. 0712345678 or +254712345678.",
        )

    if cleaned.startswith("0"):
        cleaned = "+254" + cleaned[1:]

    return cleaned


def acquire_leave_lock(db):
    """
    Serialises leave-capacity operations on PostgreSQL.
    SQLite local development skips this PostgreSQL-specific lock.
    """
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": 72619431},
        )


def get_overlapping_requests(db, start_date, end_date, exclude_id=None):
    query = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.status.in_(ACTIVE_STATUSES))
        .filter(LeaveRequest.start_date <= end_date)
        .filter(LeaveRequest.end_date >= start_date)
    )

    if exclude_id:
        query = query.filter(LeaveRequest.id != exclude_id)

    return query.all()


def check_daily_capacity(db, start_date, end_date, exclude_id=None):
    existing = get_overlapping_requests(
        db, start_date, end_date, exclude_id
    )

    current_date = start_date

    while current_date <= end_date:
        employees_on_leave = {
            request.user_id
            for request in existing
            if request.start_date <= current_date <= request.end_date
        }

        if len(employees_on_leave) >= MAX_EMPLOYEES_PER_DAY:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Leave capacity has been reached for "
                    f"{current_date.strftime('%d %B %Y')}. "
                    f"Only {MAX_EMPLOYEES_PER_DAY} employees "
                    "can be on leave per day."
                ),
            )

        current_date += timedelta(days=1)


def check_employee_overlap(
    db, user_id, start_date, end_date, exclude_id=None
):
    query = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == user_id)
        .filter(LeaveRequest.status.in_(ACTIVE_STATUSES))
        .filter(LeaveRequest.start_date <= end_date)
        .filter(LeaveRequest.end_date >= start_date)
    )

    if exclude_id:
        query = query.filter(LeaveRequest.id != exclude_id)

    if query.first():
        raise HTTPException(
            status_code=400,
            detail="You already have a pending, under-review or approved leave request covering some of these dates.",
        )


@router.get("/balance", response_model=LeaveBalanceResponse)
def get_leave_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()

    approved_this_year = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
        .filter(LeaveRequest.status == LeaveStatusEnum.approved)
        .filter(LeaveRequest.start_date >= date(today.year, 1, 1))
        .filter(LeaveRequest.start_date <= date(today.year, 12, 31))
        .all()
    )

    days_used = sum(
        days_in(r) for r in approved_this_year
        if r.leave_type != "menstrual"
    )

    menstrual_days_used = sum(
        days_in(r) for r in approved_this_year
        if r.leave_type == "menstrual"
        and r.start_date.month == today.month
    )

    return LeaveBalanceResponse(
        year=today.year,
        annual_allowance=ANNUAL_ALLOWANCE,
        days_used=days_used,
        days_remaining=max(0, ANNUAL_ALLOWANCE - days_used),
        menstrual_month=today.strftime("%B"),
        menstrual_days_used=menstrual_days_used,
        menstrual_days_remaining=max(
            0, MENSTRUAL_MONTHLY_CAP - menstrual_days_used
        ),
    )


@router.post("/", response_model=LeaveRequestResponse)
def submit_leave_request(
    leave: LeaveRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if leave.start_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Start date cannot be in the past",
        )

    if leave.end_date < leave.start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before the start date",
        )

    if not leave.emergency_contact_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Emergency contact name is required.",
        )

    phone = normalize_kenyan_phone(
        leave.emergency_contact_phone
    )

    requested_days = days_in(leave)

    acquire_leave_lock(db)

    # Prevent the employee from booking overlapping dates.
    check_employee_overlap(
        db,
        current_user.id,
        leave.start_date,
        leave.end_date,
    )

    # Enforce organisation-wide daily capacity.
    check_daily_capacity(
        db,
        leave.start_date,
        leave.end_date,
    )

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
            raise HTTPException(
                status_code=400,
                detail=f"Menstrual leave cannot exceed {MENSTRUAL_MONTHLY_CAP} days",
            )

        already = sum(
            days_in(e)
            for e in approved_existing
            if e.leave_type == "menstrual"
            and e.start_date.month == leave.start_date.month
        )

        if already + requested_days > MENSTRUAL_MONTHLY_CAP:
            raise HTTPException(
                status_code=400,
                detail=f"Only {MENSTRUAL_MONTHLY_CAP - already} menstrual leave day(s) left this month",
            )

    else:
        days_used = sum(
            days_in(e)
            for e in approved_existing
            if e.leave_type != "menstrual"
        )

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
        emergency_contact_name=leave.emergency_contact_name.strip(),
        emergency_contact_phone=phone,
    )

    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)

    return new_leave


@router.get("/mine", response_model=list[LeaveRequestResponse])
def my_leave_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(LeaveRequest)
        .filter(LeaveRequest.user_id == current_user.id)
        .order_by(LeaveRequest.submitted_at.desc())
        .all()
    )


@router.get("/", response_model=list[LeaveRequestResponse])
def list_leave_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr_or_superadmin),
):
    query = db.query(LeaveRequest).join(
        User, LeaveRequest.user_id == User.id
    )

    # HR cannot see requests submitted by HR employees.
    # Superadmins can see every request.
    if current_user.role != RoleEnum.superadmin:
        query = (
            query.outerjoin(User.department)
            .filter(
                or_(
                    User.department_id.is_(None),
                    func.lower(func.trim(User.department.property.mapper.class_.name))
                    != "hr",
                )
            )
        )

    return query.order_by(LeaveRequest.submitted_at.desc()).all()


@router.patch("/{leave_id}/review", response_model=LeaveRequestResponse)
def review_leave_request(
    leave_id: uuid.UUID,
    status: LeaveStatusEnum,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hr_or_superadmin),
):
    if status == LeaveStatusEnum.pending:
        raise HTTPException(
            status_code=400,
            detail="Status must be approved or rejected",
        )

    acquire_leave_lock(db)

    leave = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.id == leave_id)
        .with_for_update()
        .first()
    )

    if not leave:
        raise HTTPException(
            status_code=404,
            detail="Leave request not found",
        )

    applicant = db.query(User).filter(
        User.id == leave.user_id
    ).first()

    if not applicant:
        raise HTTPException(
            status_code=404,
            detail="Applicant not found",
        )

    # HR cannot review HR employees' requests.
    if is_hr(applicant) and current_user.role != RoleEnum.superadmin:
        raise HTTPException(
            status_code=403,
            detail="Only a superadmin can review HR employees' leave requests.",
        )

    # An employee cannot review their own request.
    if applicant.id == current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot review your own leave request.",
        )

    # Recheck capacity before approval.
    if status == LeaveStatusEnum.approved:
        check_daily_capacity(
            db,
            leave.start_date,
            leave.end_date,
            exclude_id=leave.id,
        )

        # Prevent another active request from overlapping
        # this employee's leave.
        check_employee_overlap(
            db,
            leave.user_id,
            leave.start_date,
            leave.end_date,
            exclude_id=leave.id,
        )

    leave.status = status
    leave.reviewed_by = current_user.id

    db.commit()
    db.refresh(leave)

    return leave
