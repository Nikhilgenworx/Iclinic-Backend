from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.appointment import Appointment


class AppointmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, appointment: Appointment) -> None:
        self.db.add(appointment)

    def get_by_id(self, appointment_id: UUID) -> Appointment | None:
        return (
            self.db.query(Appointment)
            .filter(Appointment.appointment_id == appointment_id)
            .first()
        )

    def get_by_patient(self, patient_id: UUID) -> list[Appointment]:
        return (
            self.db.query(Appointment)
            .filter(Appointment.patient_id == patient_id)
            .order_by(Appointment.start_datetime.desc())
            .all()
        )

    def get_by_doctor(self, doctor_id: UUID) -> list[Appointment]:
        return (
            self.db.query(Appointment)
            .filter(Appointment.doctor_id == doctor_id)
            .order_by(Appointment.start_datetime.asc())
            .all()
        )

    def get_by_doctor_and_date_range(
        self, doctor_id: UUID, start: datetime, end: datetime
    ) -> list[Appointment]:
        """Get appointments for a doctor that overlap with the given time range."""
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.start_datetime < end,
                Appointment.end_datetime > start,
                Appointment.status.in_(["BOOKED", "COMPLETED"]),
            )
            .order_by(Appointment.start_datetime.asc())
            .all()
        )

    def get_by_doctor_and_date(
        self, doctor_id: UUID, date: datetime
    ) -> list[Appointment]:
        """Get all appointments for a doctor on a specific date."""
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self.get_by_doctor_and_date_range(doctor_id, day_start, day_end)

    def get_by_status(self, status: str) -> list[Appointment]:
        return self.db.query(Appointment).filter(Appointment.status == status).all()

    def update_status(self, appointment: Appointment, status: str) -> None:
        appointment.status = status

    def delete(self, appointment: Appointment) -> None:
        self.db.delete(appointment)
