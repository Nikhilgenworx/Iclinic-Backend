from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from src.api.rest.dependencies import CurrentUser, DBSession
from src.core.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


class StartConversationRequest(BaseModel):
    patient_id: UUID
    channel: str  # CHAT or VOICE


class AddMessageRequest(BaseModel):
    sender_type: str  # PATIENT, AI, STAFF, SYSTEM
    sender_id: UUID
    message_type: str
    content: str


def _conversation_response(c):
    return {
        "conversation_id": str(c.conversation_id),
        "patient_id": str(c.patient_id),
        "channel": c.channel,
        "status": c.status,
        "started_at": c.started_at.isoformat(),
        "ended_at": c.ended_at.isoformat() if c.ended_at else None,
        "created_at": c.created_at.isoformat(),
    }


def _message_response(m):
    return {
        "message_id": str(m.message_id),
        "conversation_id": str(m.conversation_id),
        "sender_type": m.sender_type,
        "sender_id": str(m.sender_id),
        "message_type": m.message_type,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
    }


@router.post("", status_code=201)
def start_conversation(
    request: StartConversationRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Start or resume a conversation."""
    service = ConversationService(db)
    c = service.start_conversation(
        patient_id=request.patient_id, channel=request.channel
    )
    return _conversation_response(c)


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = ConversationService(db)
    c = service.get_conversation(conversation_id)
    return _conversation_response(c)


@router.get("/patient/{patient_id}")
def get_patient_conversations(
    patient_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = ConversationService(db)
    conversations = service.get_patient_conversations(patient_id)
    return [_conversation_response(c) for c in conversations]


@router.put("/{conversation_id}/end")
def end_conversation(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = ConversationService(db)
    c = service.end_conversation(conversation_id)
    return _conversation_response(c)


@router.post("/{conversation_id}/messages", status_code=201)
def add_message(
    conversation_id: UUID,
    request: AddMessageRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Add a message to a conversation."""
    service = ConversationService(db)
    m = service.add_message(
        conversation_id=conversation_id,
        sender_type=request.sender_type,
        sender_id=request.sender_id,
        message_type=request.message_type,
        content=request.content,
    )
    return _message_response(m)


@router.get("/{conversation_id}/messages")
def get_messages(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = ConversationService(db)
    messages = service.get_messages(conversation_id)
    return [_message_response(m) for m in messages]
