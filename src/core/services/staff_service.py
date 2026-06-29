from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.staff import Staff
from src.data.repositories.staff_repository import StaffRepository


class StaffService:
    def __init__(self, db: Session):
        self.db = db
        self.staff_repo = StaffRepository(db)

    def create_staff(
        self,
        auth_user_id: str,
        full_name: str,
        email: str,
        phone: str | None = None,
    ) -> Staff:
        existing = self.staff_repo.get_by_auth_user_id(auth_user_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Staff profile already exists for this user",
            )

        staff = Staff(
            auth_user_id=auth_user_id,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        self.staff_repo.add(staff)
        self.db.flush()
        return staff

    def get_staff(self, staff_id: UUID) -> Staff:
        staff = self.staff_repo.get_by_id(staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff not found",
            )
        return staff

    def get_staff_by_auth_user(self, auth_user_id: str) -> Staff:
        staff = self.staff_repo.get_by_auth_user_id(auth_user_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff profile not found",
            )
        return staff

    def get_all_active_staff(self) -> list[Staff]:
        return self.staff_repo.get_all_active()

    def update_staff(
        self,
        staff_id: UUID,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Staff:
        staff = self.get_staff(staff_id)

        if full_name:
            staff.full_name = full_name
        if email:
            staff.email = email
        if phone is not None:
            staff.phone = phone

        return staff

    def deactivate_staff(self, staff_id: UUID) -> None:
        staff = self.get_staff(staff_id)
        self.staff_repo.deactivate(staff)
