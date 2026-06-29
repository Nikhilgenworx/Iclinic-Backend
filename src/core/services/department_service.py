from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.department import Department
from src.data.repositories.department_repository import DepartmentRepository


class DepartmentService:
    def __init__(self, db: Session):
        self.db = db
        self.department_repo = DepartmentRepository(db)

    def create_department(
        self, name: str, description: str | None = None
    ) -> Department:
        existing = self.department_repo.get_by_name(name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department '{name}' already exists",
            )

        department = Department(name=name, description=description)
        self.department_repo.add(department)
        self.db.flush()
        return department

    def get_department(self, department_id: UUID) -> Department:
        department = self.department_repo.get_by_id(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found",
            )
        return department

    def get_all_departments(self) -> list[Department]:
        return self.department_repo.get_all()

    def update_department(
        self,
        department_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Department:
        department = self.get_department(department_id)

        if name and name != department.name:
            existing = self.department_repo.get_by_name(name)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department '{name}' already exists",
                )
            department.name = name

        if description is not None:
            department.description = description

        return department

    def delete_department(self, department_id: UUID) -> None:
        department = self.get_department(department_id)
        self.department_repo.delete(department)
