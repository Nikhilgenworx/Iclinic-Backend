from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.doctor import Doctor


class DoctorRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, doctor: Doctor) -> None:
        self.db.add(doctor)

    def get_by_id(self, doctor_id: UUID) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()

    def get_by_auth_user_id(self, auth_user_id: str) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.auth_user_id == auth_user_id).first()

    def get_by_department(self, department_id: UUID) -> list[Doctor]:
        return (
            self.db.query(Doctor)
            .filter(Doctor.department_id == department_id, Doctor.active == True)  # noqa: E712
            .all()
        )

    def get_by_specialization(self, specialization: str) -> list[Doctor]:
        # Try exact-ish match first
        results = (
            self.db.query(Doctor)
            .filter(
                Doctor.specialization.ilike(f"%{specialization}%"),
                Doctor.active == True,  # noqa: E712
            )
            .all()
        )

        # If no results, try matching first word only (e.g. "General" from "General Consultation")
        if not results and " " in specialization:
            first_word = specialization.split()[0]
            results = (
                self.db.query(Doctor)
                .filter(
                    Doctor.specialization.ilike(f"%{first_word}%"),
                    Doctor.active == True,  # noqa: E712
                )
                .all()
            )

        return results

    def get_all_active(self) -> list[Doctor]:
        return (
            self.db.query(Doctor)
            .filter(Doctor.active == True)  # noqa: E712
            .all()
        )

    def deactivate(self, doctor: Doctor) -> None:
        doctor.active = False

    def delete(self, doctor: Doctor) -> None:
        self.db.delete(doctor)
