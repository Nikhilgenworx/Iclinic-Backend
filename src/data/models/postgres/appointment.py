import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.patient_id"), nullable=False
    )

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doctors.doctor_id"), nullable=False
    )

    appointment_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointment_types.appointment_type_id"), nullable=False
    )

    start_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    end_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(String(50), default="BOOKED", nullable=False)

    booking_source: Mapped[str] = mapped_column(String(50), nullable=False)

    created_by_actor_type: Mapped[str] = mapped_column(String(50), nullable=False)

    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    appointment_type = relationship("AppointmentType", back_populates="appointments")
    notifications = relationship("Notification", back_populates="appointment")
