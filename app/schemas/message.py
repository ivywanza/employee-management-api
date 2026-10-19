import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BroadcastRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)
    content: str = Field(min_length=1, max_length=2000)


class RoomMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class DirectMessageRequest(BaseModel):
    recipient_id: uuid.UUID
    content: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    kind: str
    sender_id: uuid.UUID
    sender_name: str
    recipient_id: Optional[uuid.UUID]
    title: Optional[str]
    content: str
    created_at: datetime
    read_at: Optional[datetime]


class ConversationResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    last_message: str
    last_at: datetime
    unread: int


class PersonResponse(BaseModel):
    id: uuid.UUID
    full_name: str