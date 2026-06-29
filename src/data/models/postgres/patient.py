import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=True, index=True
    )

    first_name: Mapped[str] = mapped_column(String(255), nullable=False)

    last_name: Mapped[str] = mapped_column(String(255), nullable=False)

    phone: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    dob: Mapped[date | None] = mapped_column(Date, nullable=True)

    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    appointments = relationship("Appointment", back_populates="patient")
    conversations = relationship("Conversation", back_populates="patient")
