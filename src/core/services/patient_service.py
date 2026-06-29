from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.patient import Patient
from src.data.repositories.patient_repository import PatientRepository


class PatientService:
    def __init__(self, db: Session):
        self.db = db
        self.patient_repo = PatientRepository(db)

    def create_patient(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        email: str | None = None,
        dob: date | None = None,
        gender: str | None = None,
        user_id: str | UUID | None = None,
    ) -> Patient:
        # Check if phone already registered
        existing = self.patient_repo.get_by_phone(phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Patient with this phone number already exists",
            )

        if email:
            existing_email = self.patient_repo.get_by_email(email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Patient with this email already exists",
                )

        patient = Patient(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            dob=dob,
            gender=gender,
            user_id=UUID(str(user_id)) if user_id else None,
        )
        self.patient_repo.add(patient)
        self.db.flush()
        return patient

    def get_patient(self, patient_id: UUID) -> Patient:
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )
        return patient

    def get_patient_by_phone(self, phone: str) -> Patient | None:
        return self.patient_repo.get_by_phone(phone)

    def get_patient_by_user_id(self, user_id: str | UUID) -> Patient | None:
        return self.patient_repo.get_by_user_id(UUID(str(user_id)))

    def get_or_create_patient(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        email: str | None = None,
        dob: date | None = None,
        gender: str | None = None,
    ) -> Patient:
        """Used by AI agent — find existing patient by phone or create new."""
        existing = self.patient_repo.get_by_phone(phone)
        if existing:
            return existing

        return self.create_patient(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            dob=dob,
            gender=gender,
        )

    def get_all_patients(self) -> list[Patient]:
        return self.patient_repo.get_all()

    def update_patient(
        self,
        patient_id: UUID,
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        dob: date | None = None,
        gender: str | None = None,
    ) -> Patient:
        patient = self.get_patient(patient_id)

        if first_name:
            patient.first_name = first_name
        if last_name:
            patient.last_name = last_name
        if phone and phone != patient.phone:
            existing = self.patient_repo.get_by_phone(phone)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number already in use",
                )
            patient.phone = phone
        if email is not None:
            patient.email = email
        if dob is not None:
            patient.dob = dob
        if gender is not None:
            patient.gender = gender

        return patient

    def delete_patient(self, patient_id: UUID) -> None:
        patient = self.get_patient(patient_id)
        self.patient_repo.delete(patient)
