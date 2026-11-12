
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SaleCreate(BaseModel):
    item: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    month: date

    @field_validator("item")
    @classmethod
    def validate_item(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Sales item cannot be empty")
        return value

    @field_validator("month")
    @classmethod
    def validate_month(cls, value):
        if value.day != 1:
            raise ValueError("Month must be the first day of the reporting month")
        return value


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    item: str
    amount: Decimal
    month: date
    created_at: datetime
    updated_at: datetime


class SaleReviewResponse(SaleResponse):
    associate_name: str
    associate_email: str
