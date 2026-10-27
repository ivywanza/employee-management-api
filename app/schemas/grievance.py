
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.grievance import (
    GrievanceCategory,
    GrievanceKind,
    GrievanceStatus,
)


class GrievanceCreate(BaseModel):
    kind: GrievanceKind
    category: GrievanceCategory
    subject: Optional[str] = Field(default=None, max_length=120)
    body: str = Field(min_length=10, max_length=3000)


class GrievanceUpdate(BaseModel):
    status: GrievanceStatus
    admin_note: Optional[str] = Field(default=None, max_length=5000)


class GrievanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: GrievanceKind
    category: GrievanceCategory
    subject: Optional[str]
    body: str
    status: GrievanceStatus
    admin_note: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
