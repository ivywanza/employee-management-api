from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base  # ADAPT


class Requisition(Base):
    __tablename__ = "requisitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # REQ-2026-0001

    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # ADAPT table name

    # Snapshot of the details as printed on the form
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120))
    contact_number: Mapped[str] = mapped_column(String(30))
    department: Mapped[str] = mapped_column(String(80))

    purpose: Mapped[str] = mapped_column(Text)
    payment_method: Mapped[str] = mapped_column(String(20))
    account_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | rejected
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())