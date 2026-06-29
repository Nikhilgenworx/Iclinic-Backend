import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False
    )

    channel: Mapped[str] = mapped_column(String(50), nullable=False)

    status: Mapped[str] = mapped_column(String(50), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    patient = relationship("Patient", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation")
