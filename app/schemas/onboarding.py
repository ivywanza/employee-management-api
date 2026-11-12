import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class OnboardingDocumentRequest(BaseModel):
    user_id: uuid.UUID
    file_key: str
    document_type: Optional[str] = None


class OnboardingDocumentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    file_key: str
    document_type: Optional[str]
    reviewed: bool
    uploaded_at: datetime
    organisation: Optional[str] = None
    applicant_name: Optional[str] = None

    class Config:
        from_attributes = True