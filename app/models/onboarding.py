import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class OnboardingDocument(Base):
    __tablename__ = "onboarding_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_key = Column(String, nullable=False)
    document_type = Column(String, nullable=True)  # e.g. "ID", "Certificate", "Contract"
    reviewed = Column(Boolean, default=False, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="onboarding_documents")