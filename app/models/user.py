import uuid
import enum
from datetime import date, datetime
from sqlalchemy import Column, String, Date, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    employee = "employee"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.employee)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    start_date = Column(String, default=date.today, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    department = relationship("Department", back_populates="employees")
    documents_uploaded = relationship("Document", back_populates="uploaded_by_user")
    onboarding_documents = relationship("OnboardingDocument", back_populates="user")
    leave_requests = relationship("LeaveRequest", back_populates="user", foreign_keys="[LeaveRequest.user_id]")

    