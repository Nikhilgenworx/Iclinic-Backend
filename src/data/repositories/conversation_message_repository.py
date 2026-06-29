from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.conversation_message import ConversationMessage


class ConversationMessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, message: ConversationMessage) -> None:
        self.db.add(message)

    def get_by_id(self, message_id: UUID) -> ConversationMessage | None:
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.message_id == message_id)
            .first()
        )

    def get_by_conversation(self, conversation_id: UUID) -> list[ConversationMessage]:
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
            .all()
        )

    def get_recent_by_conversation(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[ConversationMessage]:
        return (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
            .all()
        )[::-1]  # Reverse to get chronological order

    def delete(self, message: ConversationMessage) -> None:
        self.db.delete(message)
