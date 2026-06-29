from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.rest.dependencies import DBSession, require_role
from src.core.services.staff_service import StaffService

router = APIRouter(prefix="/staff", tags=["Staff"])


class CreateStaffRequest(BaseModel):
    auth_user_id: str
    full_name: str
    email: str
    phone: str | None = None


class UpdateStaffRequest(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


def _staff_response(s):
    return {
        "staff_id": str(s.staff_id),
        "auth_user_id": s.auth_user_id,
        "full_name": s.full_name,
        "email": s.email,
        "phone": s.phone,
        "active": s.active,
        "created_at": s.created_at.isoformat(),
    }


@router.get("")
def get_all_staff(
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    """Get all active staff. Admin only."""
    service = StaffService(db)
    staff_list = service.get_all_active_staff()
    return [_staff_response(s) for s in staff_list]


@router.get("/{staff_id}")
def get_staff(
    staff_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    service = StaffService(db)
    s = service.get_staff(staff_id)
    return _staff_response(s)


@router.post("", status_code=201)
def create_staff(
    request: CreateStaffRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    """Create a staff profile. Admin only."""
    service = StaffService(db)
    s = service.create_staff(
        auth_user_id=request.auth_user_id,
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
    )
    return _staff_response(s)


@router.put("/{staff_id}")
def update_staff(
    staff_id: UUID,
    request: UpdateStaffRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    service = StaffService(db)
    s = service.update_staff(
        staff_id=staff_id,
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
    )
    return _staff_response(s)


@router.delete("/{staff_id}", status_code=204)
def deactivate_staff(
    staff_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = StaffService(db)
    service.deactivate_staff(staff_id)
