import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class Department(Base):
    __tablename__ = "departments"

    department_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    doctors = relationship("Doctor", back_populates="department")
