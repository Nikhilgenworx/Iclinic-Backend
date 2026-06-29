from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.rest.dependencies import CurrentUser, DBSession, require_role
from src.data.models.postgres.appointment_type import AppointmentType
from src.data.repositories.appointment_type_repository import AppointmentTypeRepository

router = APIRouter(prefix="/appointment-types", tags=["Appointment Types"])


class CreateAppointmentTypeRequest(BaseModel):
    name: str
    default_duration_minutes: int
    is_emergency: bool = False


def _type_response(t: AppointmentType):
    return {
        "appointment_type_id": str(t.appointment_type_id),
        "name": t.name,
        "default_duration_minutes": t.default_duration_minutes,
        "is_emergency": t.is_emergency,
        "active": t.active,
        "created_at": t.created_at.isoformat(),
    }


@router.get("")
def get_all_appointment_types(current_user: CurrentUser, db: DBSession):
    """Get all active appointment types. Accessible by all authenticated users."""
    repo = AppointmentTypeRepository(db)
    types = repo.get_all_active()
    return [_type_response(t) for t in types]


@router.get("/{type_id}")
def get_appointment_type(type_id: UUID, current_user: CurrentUser, db: DBSession):
    repo = AppointmentTypeRepository(db)
    t = repo.get_by_id(type_id)
    if not t:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment type not found",
        )
    return _type_response(t)


@router.post("", status_code=201)
def create_appointment_type(
    request: CreateAppointmentTypeRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """Create an appointment type. Admin/Front Desk only."""
    repo = AppointmentTypeRepository(db)
    t = AppointmentType(
        name=request.name,
        default_duration_minutes=request.default_duration_minutes,
        is_emergency=request.is_emergency,
    )
    repo.add(t)
    db.flush()
    return _type_response(t)


@router.delete("/{type_id}", status_code=204)
def deactivate_appointment_type(
    type_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    repo = AppointmentTypeRepository(db)
    t = repo.get_by_id(type_id)
    if t:
        repo.deactivate(t)
