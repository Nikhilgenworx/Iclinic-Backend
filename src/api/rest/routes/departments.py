from uuid import UUID

from fastapi import APIRouter, Depends
from src.api.rest.dependencies import CurrentUser, DBSession, require_role
from src.core.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("")
def get_all_departments(
    current_user: CurrentUser,
    db: DBSession,
):
    """Get all departments. Accessible by all authenticated users."""
    service = DepartmentService(db)
    departments = service.get_all_departments()
    return [
        {
            "department_id": str(d.department_id),
            "name": d.name,
            "description": d.description,
            "created_at": d.created_at.isoformat(),
        }
        for d in departments
    ]


@router.get("/{department_id}")
def get_department(
    department_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = DepartmentService(db)
    d = service.get_department(department_id)
    return {
        "department_id": str(d.department_id),
        "name": d.name,
        "description": d.description,
        "created_at": d.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_department(
    name: str,
    db: DBSession,
    description: str | None = None,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """Create a department. Admin/Front Desk only."""
    service = DepartmentService(db)
    d = service.create_department(name=name, description=description)
    return {
        "department_id": str(d.department_id),
        "name": d.name,
        "description": d.description,
        "created_at": d.created_at.isoformat(),
    }


@router.put("/{department_id}")
def update_department(
    department_id: UUID,
    db: DBSession,
    name: str | None = None,
    description: str | None = None,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    service = DepartmentService(db)
    d = service.update_department(department_id, name=name, description=description)
    return {
        "department_id": str(d.department_id),
        "name": d.name,
        "description": d.description,
    }


@router.delete("/{department_id}", status_code=204)
def delete_department(
    department_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = DepartmentService(db)
    service.delete_department(department_id)
