
import uuid
import enum
from datetime import date, datetime

from sqlalchemy import Column, String, Date, DateTime, Boolean, ForeignKey, Enum, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    """
    System roles:
    superadmin - Full system access.
    admin      - Administrative access, including requisition approvals.
    hr         - Administrative access, except requisition approvals and own leave approval.
    employee   - Standard employee access.
    """
    superadmin = "superadmin"
    admin = "admin"
    hr = "hr"
    employee = "employee"


class User(Base):
    """
    Stores employee accounts, roles and organisation assignments.
    """

    __tablename__ = "users"

    # Unique employee identifier.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Employee identity and login credentials.
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    # Employee role and department.
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.employee)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)

    # Employment information.
    start_date = Column(String, default=date.today, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # First-login and onboarding controls.
    must_change_password = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    onboarding_required = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    welcome_shown = Column(Boolean, nullable=False, default=True, server_default=text("true"))

    # Determines organisation-specific branding and dashboard features.
    organisation = Column(String(50), nullable=False, default="red_ant", server_default=text("'red_ant'"))

    # Relationships with other system records.
    department = relationship("Department", back_populates="employees")
    documents_uploaded = relationship("Document", back_populates="uploaded_by_user")
    onboarding_documents = relationship("OnboardingDocument", back_populates="user")
    leave_requests = relationship("LeaveRequest", back_populates="user", foreign_keys="[LeaveRequest.user_id]")
