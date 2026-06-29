from datetime import time
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.rest.dependencies import CurrentUser, DBSession, require_role
from src.core.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


class CreateDoctorRequest(BaseModel):
    department_id: UUID
    auth_user_id: str
    full_name: str
    specialization: str
    email: str
    phone: str | None = None
    working_start_time: time
    working_end_time: time


class UpdateDoctorRequest(BaseModel):
    full_name: str | None = None
    specialization: str | None = None
    email: str | None = None
    phone: str | None = None
    working_start_time: time | None = None
    working_end_time: time | None = None


def _doctor_response(d):
    return {
        "doctor_id": str(d.doctor_id),
        "department_id": str(d.department_id),
        "auth_user_id": d.auth_user_id,
        "full_name": d.full_name,
        "specialization": d.specialization,
        "email": d.email,
        "phone": d.phone,
        "working_start_time": d.working_start_time.isoformat(),
        "working_end_time": d.working_end_time.isoformat(),
        "active": d.active,
        "created_at": d.created_at.isoformat(),
    }


@router.get("")
def get_all_doctors(current_user: CurrentUser, db: DBSession):
    """Get all active doctors. Accessible by all authenticated users."""
    service = DoctorService(db)
    doctors = service.get_all_active_doctors()
    return [_doctor_response(d) for d in doctors]


@router.get("/specialization/{specialization}")
def get_doctors_by_specialization(
    specialization: str, current_user: CurrentUser, db: DBSession
):
    service = DoctorService(db)
    doctors = service.get_doctors_by_specialization(specialization)
    return [_doctor_response(d) for d in doctors]


@router.get("/department/{department_id}")
def get_doctors_by_department(
    department_id: UUID, current_user: CurrentUser, db: DBSession
):
    service = DoctorService(db)
    doctors = service.get_doctors_by_department(department_id)
    return [_doctor_response(d) for d in doctors]


@router.get("/{doctor_id}")
def get_doctor(doctor_id: UUID, current_user: CurrentUser, db: DBSession):
    service = DoctorService(db)
    d = service.get_doctor(doctor_id)
    return _doctor_response(d)


@router.post("", status_code=201)
def create_doctor(
    request: CreateDoctorRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """Create a doctor profile. Admin/Front Desk only."""
    service = DoctorService(db)
    d = service.create_doctor(
        department_id=request.department_id,
        auth_user_id=request.auth_user_id,
        full_name=request.full_name,
        specialization=request.specialization,
        email=request.email,
        phone=request.phone,
        working_start_time=request.working_start_time,
        working_end_time=request.working_end_time,
    )
    return _doctor_response(d)


@router.put("/{doctor_id}")
def update_doctor(
    doctor_id: UUID,
    request: UpdateDoctorRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    service = DoctorService(db)
    d = service.update_doctor(
        doctor_id=doctor_id,
        full_name=request.full_name,
        specialization=request.specialization,
        email=request.email,
        phone=request.phone,
        working_start_time=request.working_start_time,
        working_end_time=request.working_end_time,
    )
    return _doctor_response(d)


@router.delete("/{doctor_id}", status_code=204)
def deactivate_doctor(
    doctor_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = DoctorService(db)
    service.deactivate_doctor(doctor_id)
