
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, String, Text

from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class GrievanceKind(str, enum.Enum):
    comment = "comment"
    complaint = "complaint"


class GrievanceCategory(str, enum.Enum):
    workplace = "workplace"
    management = "management"
    facilities = "facilities"
    safety = "safety"
    pay_benefits = "pay_benefits"
    harassment = "harassment"
    other = "other"


class GrievanceStatus(str, enum.Enum):
    new = "new"
    in_review = "in_review"
    resolved = "resolved"
    dismissed = "dismissed"


class Grievance(Base):
    __tablename__ = "grievances"

    id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4,)
    kind = Column(Enum(GrievanceKind, name="grievance_kind"),nullable=False,)
    category = Column(Enum(GrievanceCategory, name="grievance_category"),nullable=False,)
    subject = Column(String(120), nullable=True)
    body = Column(Text, nullable=False)
    status = Column(Enum(GrievanceStatus, name="grievance_status"),nullable=False,default=GrievanceStatus.new,)
    admin_note = Column(Text, nullable=True)
    # Deliberately rounded down to the hour on submission.
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)
