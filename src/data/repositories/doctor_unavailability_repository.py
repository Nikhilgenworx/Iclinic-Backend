from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.doctor_unavailability import DoctorUnavailability


class DoctorUnavailabilityRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, unavailability: DoctorUnavailability) -> None:
        self.db.add(unavailability)

    def get_by_id(self, unavailability_id: UUID) -> DoctorUnavailability | None:
        return (
            self.db.query(DoctorUnavailability)
            .filter(DoctorUnavailability.unavailability_id == unavailability_id)
            .first()
        )

    def get_by_doctor(self, doctor_id: UUID) -> list[DoctorUnavailability]:
        return (
            self.db.query(DoctorUnavailability)
            .filter(DoctorUnavailability.doctor_id == doctor_id)
            .all()
        )

    def get_by_doctor_and_date_range(
        self, doctor_id: UUID, start: datetime, end: datetime
    ) -> list[DoctorUnavailability]:
        """Get unavailability blocks that overlap with the given time range."""
        return (
            self.db.query(DoctorUnavailability)
            .filter(
                DoctorUnavailability.doctor_id == doctor_id,
                DoctorUnavailability.start_datetime < end,
                DoctorUnavailability.end_datetime > start,
            )
            .all()
        )

    def delete(self, unavailability: DoctorUnavailability) -> None:
        self.db.delete(unavailability)
