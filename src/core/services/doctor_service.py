from datetime import time
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.doctor import Doctor
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.doctor_repository import DoctorRepository


class DoctorService:
    def __init__(self, db: Session):
        self.db = db
        self.doctor_repo = DoctorRepository(db)
        self.department_repo = DepartmentRepository(db)

    def create_doctor(
        self,
        department_id: UUID,
        auth_user_id: str,
        full_name: str,
        specialization: str,
        email: str,
        working_start_time: time,
        working_end_time: time,
        phone: str | None = None,
    ) -> Doctor:
        # Validate department exists
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )

        # Check duplicate auth_user_id
        existing = self.doctor_repo.get_by_auth_user_id(auth_user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor profile already exists for this user",
            )

        doctor = Doctor(
            department_id=department_id,
            auth_user_id=auth_user_id,
            full_name=full_name,
            specialization=specialization,
            email=email,
            phone=phone,
            working_start_time=working_start_time,
            working_end_time=working_end_time,
        )
        self.doctor_repo.add(doctor)
        self.db.flush()
        return doctor

    def get_doctor(self, doctor_id: UUID) -> Doctor:
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )
        return doctor

    def get_doctor_by_auth_user(self, auth_user_id: str) -> Doctor:
        doctor = self.doctor_repo.get_by_auth_user_id(auth_user_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor profile not found",
            )
        return doctor

    def get_doctors_by_specialization(self, specialization: str) -> list[Doctor]:
        return self.doctor_repo.get_by_specialization(specialization)

    def get_doctors_by_department(self, department_id: UUID) -> list[Doctor]:
        return self.doctor_repo.get_by_department(department_id)

    def get_all_active_doctors(self) -> list[Doctor]:
        return self.doctor_repo.get_all_active()

    def update_doctor(
        self,
        doctor_id: UUID,
        full_name: str | None = None,
        specialization: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        working_start_time: time | None = None,
        working_end_time: time | None = None,
    ) -> Doctor:
        doctor = self.get_doctor(doctor_id)

        if full_name:
            doctor.full_name = full_name
        if specialization:
            doctor.specialization = specialization
        if email:
            doctor.email = email
        if phone is not None:
            doctor.phone = phone
        if working_start_time:
            doctor.working_start_time = working_start_time
        if working_end_time:
            doctor.working_end_time = working_end_time

        return doctor

    def deactivate_doctor(self, doctor_id: UUID) -> None:
        doctor = self.get_doctor(doctor_id)
        self.doctor_repo.deactivate(doctor)
