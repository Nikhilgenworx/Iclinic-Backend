import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from src.data.models.postgres.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    entity_type: Mapped[str] = mapped_column(String(255), nullable=False)

    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    action: Mapped[str] = mapped_column(String(255), nullable=False)

    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)

    actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
