import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    message_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.conversation_id"), nullable=False
    )

    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)

    sender_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    message_type: Mapped[str] = mapped_column(String(50), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
