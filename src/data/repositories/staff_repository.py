from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.staff import Staff


class StaffRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, staff: Staff) -> None:
        self.db.add(staff)

    def get_by_id(self, staff_id: UUID) -> Staff | None:
        return self.db.query(Staff).filter(Staff.staff_id == staff_id).first()

    def get_by_auth_user_id(self, auth_user_id: str) -> Staff | None:
        return self.db.query(Staff).filter(Staff.auth_user_id == auth_user_id).first()

    def get_all_active(self) -> list[Staff]:
        return (
            self.db.query(Staff)
            .filter(Staff.active == True)  # noqa: E712
            .all()
        )

    def deactivate(self, staff: Staff) -> None:
        staff.active = False

    def delete(self, staff: Staff) -> None:
        self.db.delete(staff)
