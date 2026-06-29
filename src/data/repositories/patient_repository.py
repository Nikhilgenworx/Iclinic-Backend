from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.patient import Patient


class PatientRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, patient: Patient) -> None:
        self.db.add(patient)

    def get_by_id(self, patient_id: UUID) -> Patient | None:
        return self.db.query(Patient).filter(Patient.patient_id == patient_id).first()

    def get_by_phone(self, phone: str) -> Patient | None:
        return self.db.query(Patient).filter(Patient.phone == phone).first()

    def get_by_email(self, email: str) -> Patient | None:
        return self.db.query(Patient).filter(Patient.email == email).first()

    def get_by_user_id(self, user_id: UUID) -> Patient | None:
        return self.db.query(Patient).filter(Patient.user_id == user_id).first()

    def get_all(self) -> list[Patient]:
        return self.db.query(Patient).all()

    def delete(self, patient: Patient) -> None:
        self.db.delete(patient)
