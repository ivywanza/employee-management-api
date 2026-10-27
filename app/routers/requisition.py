from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user  # ADAPT
from app.database import get_db  # ADAPT
from app.models.requisition import Requisition

router = APIRouter(prefix="/requisitions", tags=["requisitions"])

PaymentMethod = Literal["Cash", "M-Pesa", "Bank Transfer", "Cheque"]
Status = Literal["pending", "approved", "rejected"]


def _is_admin(user) -> bool:
    role = getattr(user, "role", "")
    return str(getattr(role, "value", role)).lower() in {"superadmin", "admin"}


def require_admin(user=Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Only admins can do this.")
    return user


# --------------------------------------------------------------- schemas ----
class RequisitionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=120)
    contact_number: str = Field(min_length=7, max_length=30)
    department: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=5, max_length=200)  # fits the two lines on the printed form
    payment_method: PaymentMethod
    account_number: str | None = Field(default=None, max_length=60)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class RequisitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: str
    name: str
    email: str
    contact_number: str
    department: str
    purpose: str
    payment_method: str
    account_number: str | None
    amount: Decimal  # serialised as a string by Pydantic v2; the frontend converts it
    status: Status
    reviewed_by: str | None
    reviewed_on: date | None
    created_at: datetime


class ReviewIn(BaseModel):
    status: Literal["approved", "rejected"]


# ---------------------------------------------------------------- helpers ----
def _next_number(db: Session) -> str:
    prefix = f"REQ-{date.today().year}-"
    count = db.scalar(
        select(func.count()).select_from(Requisition).where(Requisition.number.like(f"{prefix}%"))
    )
    return f"{prefix}{(count or 0) + 1:04d}"


# ----------------------------------------------------------------- routes ----
@router.post("", response_model=RequisitionOut, status_code=201)
def create_requisition(
    payload: RequisitionCreate, user=Depends(get_current_user), db: Session = Depends(get_db)
):
    data = payload.model_dump()
    if payload.payment_method == "Cash":
        data["account_number"] = None

    for _ in range(3):  # retry if two people grab the same number at once
        item = Requisition(number=_next_number(db), requester_id=user.id, **data)
        db.add(item)
        try:
            db.commit()
            db.refresh(item)
            return item
        except IntegrityError:
            db.rollback()
    raise HTTPException(status_code=409, detail="Couldn't generate a requisition number. Try again.")


@router.get("/mine", response_model=list[RequisitionOut])
def my_requisitions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Requisition).where(Requisition.requester_id == user.id)
    return db.scalars(stmt.order_by(Requisition.id.desc())).all()


@router.get("/summary")
def summary(
    year: int | None = Query(default=None, ge=2020, le=2100),
    admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Counts by status, plus approved totals per month (feeds the chart)."""
    year = year or date.today().year
    counts = dict(db.execute(select(Requisition.status, func.count()).group_by(Requisition.status)).all())

    month = func.to_char(Requisition.reviewed_on, "YYYY-MM").label("month")
    rows = db.execute(
        select(month, func.sum(Requisition.amount))
        .where(Requisition.status == "approved", func.extract("year", Requisition.reviewed_on) == year)
        .group_by(month)
        .order_by(month)
    ).all()
    approved_total = db.scalar(
        select(func.coalesce(func.sum(Requisition.amount), 0)).where(Requisition.status == "approved")
    )
    return {
        "pending": counts.get("pending", 0),
        "approved": counts.get("approved", 0),
        "rejected": counts.get("rejected", 0),
        "approved_total": float(approved_total),
        "by_month": [{"month": m, "total": float(t)} for m, t in rows],
    }


@router.get("", response_model=list[RequisitionOut])
def list_requisitions(
    status: Status | None = None, admin=Depends(require_admin), db: Session = Depends(get_db)
):
    stmt = select(Requisition)
    if status:
        stmt = stmt.where(Requisition.status == status)
    return db.scalars(stmt.order_by(Requisition.id.desc())).all()


@router.get("/{req_id}", response_model=RequisitionOut)
def get_requisition(req_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Requisition, req_id)
    if not item or (item.requester_id != user.id and not _is_admin(user)):
        raise HTTPException(status_code=404, detail="Requisition not found.")
    return item


@router.patch("/{req_id}/review", response_model=RequisitionOut)
def review_requisition(
    req_id: int, body: ReviewIn, admin=Depends(require_admin), db: Session = Depends(get_db)
):
    item = db.get(Requisition, req_id)
    if not item:
        raise HTTPException(status_code=404, detail="Requisition not found.")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {item.status}.")
    item.status = body.status
    item.reviewed_by = getattr(admin, "full_name", None) or "Admin"  # ADAPT attribute name
    item.reviewed_on = date.today()
    db.commit()
    db.refresh(item)
    return item