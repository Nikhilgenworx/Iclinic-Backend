import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.data.models.postgres.base import Base


class Doctor(Base):
    __tablename__ = "doctors"

    doctor_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.department_id"), nullable=False
    )

    auth_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    specialization: Mapped[str] = mapped_column(String(255), nullable=False)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    working_start_time: Mapped[time] = mapped_column(Time, nullable=False)

    working_end_time: Mapped[time] = mapped_column(Time, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    department = relationship("Department", back_populates="doctors")
    appointments = relationship("Appointment", back_populates="doctor")
    unavailabilities = relationship("DoctorUnavailability", back_populates="doctor")
