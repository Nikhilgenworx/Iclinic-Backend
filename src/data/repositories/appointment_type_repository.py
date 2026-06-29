from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.appointment_type import AppointmentType


class AppointmentTypeRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, appointment_type: AppointmentType) -> None:
        self.db.add(appointment_type)

    def get_by_id(self, appointment_type_id: UUID) -> AppointmentType | None:
        return (
            self.db.query(AppointmentType)
            .filter(AppointmentType.appointment_type_id == appointment_type_id)
            .first()
        )

    def get_by_name(self, name: str) -> AppointmentType | None:
        return (
            self.db.query(AppointmentType).filter(AppointmentType.name == name).first()
        )

    def get_all_active(self) -> list[AppointmentType]:
        return (
            self.db.query(AppointmentType)
            .filter(AppointmentType.active == True)  # noqa: E712
            .all()
        )

    def deactivate(self, appointment_type: AppointmentType) -> None:
        appointment_type.active = False

    def delete(self, appointment_type: AppointmentType) -> None:
        self.db.delete(appointment_type)
