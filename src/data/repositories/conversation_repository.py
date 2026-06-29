from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.conversation import Conversation


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, conversation: Conversation) -> None:
        self.db.add(conversation)

    def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(Conversation.conversation_id == conversation_id)
            .first()
        )

    def get_by_patient(self, patient_id: UUID) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.patient_id == patient_id)
            .order_by(Conversation.started_at.desc())
            .all()
        )

    def get_active_by_patient(self, patient_id: UUID) -> Conversation | None:
        return (
            self.db.query(Conversation)
            .filter(
                Conversation.patient_id == patient_id,
                Conversation.status == "ACTIVE",
            )
            .first()
        )

    def end_conversation(self, conversation: Conversation) -> None:
        from datetime import datetime

        conversation.status = "ENDED"
        conversation.ended_at = datetime.utcnow()

    def delete(self, conversation: Conversation) -> None:
        self.db.delete(conversation)
