
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AssetStatus(str, enum.Enum):
    available = "available"
    pending_assignment = "pending_assignment"
    assigned = "assigned"
    maintenance = "maintenance"
    retired = "retired"


class AssetRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_tag = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(160), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    serial_number = Column(String(160), nullable=True)
    status = Column(Enum(AssetStatus, name="asset_status"),nullable=False,default=AssetStatus.available,)
    assigned_to_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True,index=True,)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime,nullable=True,onupdate=datetime.utcnow,)
    assignment_pending_to_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True,index=True,)
    assignment_token_hash = Column(String(64), nullable=True)
    assignment_token_expires_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    assignment_accepted_at = Column(DateTime, nullable=True)
    assignment_pending_to = relationship("User",foreign_keys=[assignment_pending_to_id],)

    


    assigned_to = relationship("User", foreign_keys=[assigned_to_id])


class AssetRequest(Base):
    __tablename__ = "asset_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    requested_by_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=False,index=True,)

    asset_id = Column(UUID(as_uuid=True),ForeignKey("assets.id"),nullable=True,)

    item_name = Column(String(160), nullable=False)
    category = Column(String(100), nullable=False)
    purpose = Column(Text, nullable=False)

    status = Column(Enum(AssetRequestStatus, name="asset_request_status"),nullable=False,default=AssetRequestStatus.pending,)

    review_note = Column(Text, nullable=True)

    reviewed_by_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True,)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    requester = relationship("User", foreign_keys=[requested_by_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])
    asset = relationship("Asset", foreign_keys=[asset_id])

