import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class AppointmentType(Base):
    __tablename__ = "appointment_types"

    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    default_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    appointments = relationship("Appointment", back_populates="appointment_type")
