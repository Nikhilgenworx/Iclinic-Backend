from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.department import Department


class DepartmentRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, department: Department) -> None:
        self.db.add(department)

    def get_by_id(self, department_id: UUID) -> Department | None:
        return (
            self.db.query(Department)
            .filter(Department.department_id == department_id)
            .first()
        )

    def get_by_name(self, name: str) -> Department | None:
        return self.db.query(Department).filter(Department.name == name).first()

    def get_all(self) -> list[Department]:
        return self.db.query(Department).all()

    def delete(self, department: Department) -> None:
        self.db.delete(department)
