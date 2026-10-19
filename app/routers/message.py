import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.message import Message
from app.models.user import User
from app.schemas.message import (
    BroadcastRequest,
    RoomMessageRequest,
    DirectMessageRequest,
    ChatMessageResponse,
    ConversationResponse,
    PersonResponse,
)
from app.auth.dependencies import get_current_user, require_admin
from app.ws import manager

router = APIRouter(prefix="/messages", tags=["Messages"])


def to_response(m: Message) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=m.id,
        kind=m.kind,
        sender_id=m.sender_id,
        sender_name=m.sender.full_name,
        recipient_id=m.recipient_id,
        title=m.title,
        content=m.content,
        created_at=m.created_at,
        read_at=m.read_at,
    )


@router.post("/broadcast", response_model=ChatMessageResponse)
def send_broadcast(
    data: BroadcastRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Message can't be empty")

    msg = Message(
        kind="announcement",
        sender_id=current_user.id,
        recipient_id=None,
        title=data.title.strip() if data.title else None,
        content=data.content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    response = to_response(msg)
    background_tasks.add_task(
        manager.broadcast, {"type": "broadcast", "message": response.model_dump(mode="json")}
    )
    return response


@router.get("/broadcasts", response_model=list[ChatMessageResponse])
def list_broadcasts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(Message)
        .filter(Message.kind == "announcement")
        .order_by(Message.created_at.desc())
        .limit(50)
        .all()
    )
    return [to_response(m) for m in rows]


@router.post("/room", response_model=ChatMessageResponse)
def send_room_message(
    data: RoomMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Message can't be empty")

    msg = Message(kind="room", sender_id=current_user.id, recipient_id=None, content=data.content.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)

    response = to_response(msg)
    background_tasks.add_task(
        manager.broadcast, {"type": "room", "message": response.model_dump(mode="json")}
    )
    return response


@router.get("/room", response_model=list[ChatMessageResponse])
def list_room_messages(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(Message)
        .filter(Message.kind == "room")
        .order_by(Message.created_at.desc())
        .limit(100)
        .all()
    )
    rows.reverse()
    return [to_response(m) for m in rows]


@router.get("/people", response_model=list[PersonResponse])
def list_people(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.id != current_user.id)
        .order_by(User.full_name)
        .all()
    )
    return [PersonResponse(id=u.id, full_name=u.full_name) for u in users]


@router.post("/direct", response_model=ChatMessageResponse)
def send_direct_message(
    data: DirectMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Message can't be empty")
    if data.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="You can't message yourself")

    recipient = db.query(User).filter(User.id == data.recipient_id, User.is_active.is_(True)).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    msg = Message(kind="direct", sender_id=current_user.id, recipient_id=recipient.id, content=data.content.strip())
    db.add(msg)
    db.commit()
    db.refresh(msg)

    response = to_response(msg)
    background_tasks.add_task(
        manager.send_to_users,
        [recipient.id, current_user.id],
        {"type": "direct", "message": response.model_dump(mode="json")},
    )
    return response


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(Message)
        .filter(
            Message.kind == "direct",
            or_(Message.sender_id == current_user.id, Message.recipient_id == current_user.id),
        )
        .order_by(Message.created_at.desc())
        .all()
    )

    seen: dict[uuid.UUID, ConversationResponse] = {}
    for m in rows:
        sent_by_me = m.sender_id == current_user.id
        other = m.recipient if sent_by_me else m.sender
        entry = seen.get(other.id)
        if entry is None:
            entry = seen[other.id] = ConversationResponse(
                user_id=other.id,
                full_name=other.full_name,
                last_message=m.content,
                last_at=m.created_at,
                unread=0,
            )
        if m.recipient_id == current_user.id and m.read_at is None:
            entry.unread += 1
    return list(seen.values())


@router.get("/direct/{user_id}", response_model=list[ChatMessageResponse])
def get_conversation(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")

    thread = (
        db.query(Message)
        .filter(
            Message.kind == "direct",
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
                and_(Message.sender_id == user_id, Message.recipient_id == current_user.id),
            ),
        )
        .order_by(Message.created_at.desc())
        .limit(200)
        .all()
    )
    thread.reverse()

    now = datetime.utcnow()
    for m in thread:
        if m.recipient_id == current_user.id and m.read_at is None:
            m.read_at = now
    db.commit()
    return [to_response(m) for m in thread]