from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.conversation import Conversation
from src.data.models.postgres.conversation_message import ConversationMessage
from src.data.repositories.conversation_message_repository import (
    ConversationMessageRepository,
)
from src.data.repositories.conversation_repository import ConversationRepository
from src.data.repositories.patient_repository import PatientRepository


class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.conversation_repo = ConversationRepository(db)
        self.message_repo = ConversationMessageRepository(db)
        self.patient_repo = PatientRepository(db)

    def start_conversation(self, patient_id: UUID, channel: str) -> Conversation:
        # Validate patient
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Check if there's already an active conversation
        active = self.conversation_repo.get_active_by_patient(patient_id)
        if active:
            return active  # Reuse existing active conversation

        conversation = Conversation(
            patient_id=patient_id,
            channel=channel,
            status="ACTIVE",
            started_at=datetime.utcnow(),
        )
        self.conversation_repo.add(conversation)
        self.db.flush()
        return conversation

    def get_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    def get_patient_conversations(self, patient_id: UUID) -> list[Conversation]:
        return self.conversation_repo.get_by_patient(patient_id)

    def end_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = self.get_conversation(conversation_id)

        if conversation.status == "ENDED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conversation is already ended",
            )

        self.conversation_repo.end_conversation(conversation)
        return conversation

    def add_message(
        self,
        conversation_id: UUID,
        sender_type: str,
        sender_id: UUID,
        message_type: str,
        content: str,
    ) -> ConversationMessage:
        # Validate conversation exists
        conversation = self.get_conversation(conversation_id)

        if conversation.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add messages to an ended conversation",
            )

        message = ConversationMessage(
            conversation_id=conversation_id,
            sender_type=sender_type,
            sender_id=sender_id,
            message_type=message_type,
            content=content,
        )
        self.message_repo.add(message)
        self.db.flush()
        return message

    def get_messages(self, conversation_id: UUID) -> list[ConversationMessage]:
        return self.message_repo.get_by_conversation(conversation_id)

    def get_recent_messages(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ConversationMessage]:
        return self.message_repo.get_recent_by_conversation(conversation_id, limit)
