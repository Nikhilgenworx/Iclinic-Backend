from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from src.api.rest.dependencies import DBSession, require_role
from src.data.models.postgres.doctor_unavailability import DoctorUnavailability
from src.data.repositories.doctor_unavailability_repository import (
    DoctorUnavailabilityRepository,
)

router = APIRouter(prefix="/doctor-unavailability", tags=["Doctor Unavailability"])


class CreateUnavailabilityRequest(BaseModel):
    doctor_id: UUID
    start_datetime: datetime
    end_datetime: datetime
    reason: str | None = None


def _unavailability_response(u):
    return {
        "unavailability_id": str(u.unavailability_id),
        "doctor_id": str(u.doctor_id),
        "start_datetime": u.start_datetime.isoformat(),
        "end_datetime": u.end_datetime.isoformat(),
        "reason": u.reason,
        "created_at": u.created_at.isoformat(),
    }


@router.get("/doctor/{doctor_id}")
def get_doctor_unavailabilities(
    doctor_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    """Get all unavailability blocks for a doctor."""
    repo = DoctorUnavailabilityRepository(db)
    unavailabilities = repo.get_by_doctor(doctor_id)
    return [_unavailability_response(u) for u in unavailabilities]


@router.post("", status_code=201)
def create_unavailability(
    request: CreateUnavailabilityRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    """Create an unavailability block. Staff/Doctor only."""
    if request.start_datetime >= request.end_datetime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_datetime must be before end_datetime",
        )

    repo = DoctorUnavailabilityRepository(db)
    u = DoctorUnavailability(
        doctor_id=request.doctor_id,
        start_datetime=request.start_datetime,
        end_datetime=request.end_datetime,
        reason=request.reason,
    )
    repo.add(u)
    db.flush()
    return _unavailability_response(u)


@router.delete("/{unavailability_id}", status_code=204)
def delete_unavailability(
    unavailability_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    repo = DoctorUnavailabilityRepository(db)
    u = repo.get_by_id(unavailability_id)
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unavailability not found",
        )
    repo.delete(u)
