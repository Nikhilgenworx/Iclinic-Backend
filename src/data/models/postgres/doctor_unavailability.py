import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class DoctorUnavailability(Base):
    __tablename__ = "doctor_unavailabilities"

    unavailability_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.doctor_id"), nullable=False
    )

    start_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    end_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    doctor = relationship("Doctor", back_populates="unavailabilities")
