import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DocumentRequest(BaseModel):
    title: str
    file_key: str
    category: Optional[str] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    file_key: str
    category: Optional[str]
    uploaded_by: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True