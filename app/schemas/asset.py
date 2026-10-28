
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetStatusValue = Literal[
    "available",
    "assigned",
    "maintenance",
    "retired",
]

AssetRequestStatusValue = Literal[
    "pending",
    "approved",
    "rejected",
]


class AssetCreate(BaseModel):
    asset_tag: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    serial_number: str | None = Field(default=None, max_length=160)
    status: AssetStatusValue = "available"


class AssetUpdate(BaseModel):
    asset_tag: str | None = Field(default=None, min_length=2, max_length=80)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    serial_number: str | None = Field(default=None, max_length=160)
    status: AssetStatusValue | None = None
    assigned_to_id: uuid.UUID | None = None
    is_active: bool | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_tag: str
    name: str
    category: str
    description: str | None
    serial_number: str | None
    status: AssetStatusValue
    assigned_to_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    assigned_to_name: str | None = None


class AssetRequestCreate(BaseModel):
    item_name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    purpose: str = Field(min_length=10, max_length=3000)
    asset_id: uuid.UUID | None = None


class AssetRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=3000)
    asset_id: uuid.UUID | None = None


class AssetRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requested_by_id: uuid.UUID
    asset_id: uuid.UUID | None
    item_name: str
    category: str
    purpose: str
    status: AssetRequestStatusValue
    review_note: str | None
    reviewed_by_id: uuid.UUID | None
    created_at: datetime
    reviewed_at: datetime | None
    requester_name: str | None = None
    asset_name: str | None = None
