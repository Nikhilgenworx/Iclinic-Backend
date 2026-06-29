import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from src.data.models.postgres.base import Base


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    auth_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
