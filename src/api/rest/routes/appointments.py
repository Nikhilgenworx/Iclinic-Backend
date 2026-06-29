from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from src.api.rest.dependencies import CurrentUser, DBSession, require_role
from src.core.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


class BookAppointmentRequest(BaseModel):
    patient_id: UUID
    doctor_id: UUID
    appointment_type_id: UUID
    start_datetime: datetime
    booking_source: str  # AI_CHAT, AI_CALL, FRONT_DESK


class RescheduleRequest(BaseModel):
    new_start_datetime: datetime


class AvailabilityRequest(BaseModel):
    doctor_id: UUID
    date: datetime
    appointment_type_id: UUID


def _appointment_response(a):
    return {
        "appointment_id": str(a.appointment_id),
        "patient_id": str(a.patient_id),
        "doctor_id": str(a.doctor_id),
        "appointment_type_id": str(a.appointment_type_id),
        "start_datetime": a.start_datetime.isoformat(),
        "end_datetime": a.end_datetime.isoformat(),
        "status": a.status,
        "booking_source": a.booking_source,
        "created_by_actor_type": a.created_by_actor_type,
        "created_by_actor_id": str(a.created_by_actor_id),
        "created_at": a.created_at.isoformat(),
    }


def _appointment_response_full(a):
    """Extended response with doctor name and appointment type name."""
    resp = _appointment_response(a)
    resp["doctor_name"] = a.doctor.full_name if a.doctor else None
    resp["doctor_specialization"] = a.doctor.specialization if a.doctor else None
    resp["appointment_type_name"] = (
        a.appointment_type.name if a.appointment_type else None
    )
    return resp


@router.get("/me")
def get_my_appointments(
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get the current patient's appointments (active + history).
    Returns all appointments sorted by start_datetime descending.
    """
    from src.core.services.patient_service import PatientService

    user_id = current_user.get("sub")
    patient_service = PatientService(db)
    patient = patient_service.get_patient_by_user_id(user_id)

    if not patient:
        return {"active": [], "history": []}

    service = AppointmentService(db)
    all_appointments = service.get_patient_appointments(patient.patient_id)

    active = []
    history = []

    for a in all_appointments:
        item = _appointment_response_full(a)
        if a.status == "BOOKED":
            active.append(item)
        else:
            history.append(item)

    return {"active": active, "history": history}


@router.get("/admin/schedule")
def get_admin_schedule(
    date: str = Query(default=""),
    db: DBSession = None,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """
    Admin/Front Desk: Get all doctors' schedules for a given date.
    Returns each doctor with their working hours and booked slots
    so the frontend can render a Gantt chart.
    """
    from src.core.services.doctor_service import DoctorService
    from src.data.repositories.appointment_repository import AppointmentRepository
    from src.data.repositories.doctor_unavailability_repository import (
        DoctorUnavailabilityRepository,
    )

    # Parse date (default to today)
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()

    doctor_service = DoctorService(db)
    doctors = doctor_service.get_all_active_doctors()

    appointment_repo = AppointmentRepository(db)
    unavailability_repo = DoctorUnavailabilityRepository(db)

    schedule = []

    for doctor in doctors:
        day_start = target_date.replace(
            hour=doctor.working_start_time.hour,
            minute=doctor.working_start_time.minute,
            second=0,
            microsecond=0,
        )
        day_end = target_date.replace(
            hour=doctor.working_end_time.hour,
            minute=doctor.working_end_time.minute,
            second=0,
            microsecond=0,
        )

        # Get booked appointments
        appointments = appointment_repo.get_by_doctor_and_date_range(
            doctor.doctor_id, day_start, day_end
        )
        booked_slots = []
        for a in appointments:
            booked_slots.append(
                {
                    "appointment_id": str(a.appointment_id),
                    "patient_id": str(a.patient_id),
                    "start": a.start_datetime.isoformat(),
                    "end": a.end_datetime.isoformat(),
                    "status": a.status,
                    "patient_name": (
                        f"{a.patient.first_name} {a.patient.last_name}"
                        if a.patient
                        else None
                    ),
                }
            )

        # Get unavailability blocks
        unavailabilities = unavailability_repo.get_by_doctor_and_date_range(
            doctor.doctor_id, day_start, day_end
        )
        blocked = []
        for u in unavailabilities:
            blocked.append(
                {
                    "start": u.start_datetime.isoformat(),
                    "end": u.end_datetime.isoformat(),
                    "reason": u.reason,
                }
            )

        schedule.append(
            {
                "doctor_id": str(doctor.doctor_id),
                "doctor_name": doctor.full_name,
                "specialization": doctor.specialization,
                "working_start": day_start.isoformat(),
                "working_end": day_end.isoformat(),
                "booked_slots": booked_slots,
                "unavailability": blocked,
            }
        )

    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "doctors": schedule,
    }


class FrontDeskBookRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    doctor_id: UUID
    appointment_type_id: UUID
    start_datetime: datetime


@router.post("/frontdesk-book", status_code=201)
def frontdesk_book_appointment(
    request: FrontDeskBookRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """
    Front desk booking: Takes patient name + phone, finds or creates patient,
    books the appointment, and sends SMS confirmation.
    """
    from src.core.services.patient_service import PatientService

    patient_service = PatientService(db)

    # Try to find patient by phone
    patient = patient_service.get_patient_by_phone(request.phone)

    if not patient:
        # Try normalized phone
        stripped = request.phone.lstrip("+")
        if len(stripped) > 10:
            stripped = stripped[-10:]
        patient = patient_service.get_patient_by_phone(stripped)

    # Create patient if not found
    if not patient:
        patient = patient_service.create_patient(
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            email=None,
        )

    # Book the appointment
    service = AppointmentService(db)
    appointment = service.book_appointment(
        patient_id=patient.patient_id,
        doctor_id=request.doctor_id,
        appointment_type_id=request.appointment_type_id,
        start_datetime=request.start_datetime,
        booking_source="FRONT_DESK",
        created_by_actor_type=current_user.get("role"),
        created_by_actor_id=UUID(current_user.get("sub")),
    )

    # Send SMS confirmation
    try:
        from control.tools.sms_tool import SmsTool
        from src.data.models.postgres.doctor import Doctor

        doctor = db.query(Doctor).filter(Doctor.doctor_id == request.doctor_id).first()
        doctor_name = doctor.full_name if doctor else "Your Doctor"
        patient_name = f"{request.first_name} {request.last_name}"
        appointment_date = request.start_datetime.strftime("%A, %B %d, %Y at %I:%M %p")

        phone = request.phone.strip()
        if not phone.startswith("+"):
            phone = f"+91{phone}" if len(phone) == 10 else f"+{phone}"

        import asyncio

        sms_tool = SmsTool()
        coro = sms_tool.execute(
            to_phone=phone,
            patient_name=patient_name,
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_id=str(appointment.appointment_id),
            sms_type="confirmation",
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)
    except Exception as sms_err:
        import logging as _log

        _log.getLogger(__name__).warning(f"[FRONTDESK-BOOK] SMS failed: {sms_err}")
        # SMS failure shouldn't block the booking

    return _appointment_response(appointment)


@router.post("", status_code=201)
def book_appointment(
    request: BookAppointmentRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Book an appointment. Accessible by all authenticated users."""
    service = AppointmentService(db)
    appointment = service.book_appointment(
        patient_id=request.patient_id,
        doctor_id=request.doctor_id,
        appointment_type_id=request.appointment_type_id,
        start_datetime=request.start_datetime,
        booking_source=request.booking_source,
        created_by_actor_type=current_user.get("role"),
        created_by_actor_id=UUID(current_user.get("sub")),
    )
    return _appointment_response(appointment)


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = AppointmentService(db)
    a = service.get_appointment(appointment_id)
    return _appointment_response(a)


@router.get("/patient/{patient_id}")
def get_patient_appointments(
    patient_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = AppointmentService(db)
    appointments = service.get_patient_appointments(patient_id)
    return [_appointment_response(a) for a in appointments]


@router.get("/doctor/{doctor_id}")
def get_doctor_appointments(
    doctor_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = AppointmentService(db)
    appointments = service.get_doctor_appointments(doctor_id)
    return [_appointment_response(a) for a in appointments]


@router.post("/availability")
def get_available_slots(
    request: AvailabilityRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Get available time slots for a doctor on a given date."""
    service = AppointmentService(db)
    slots = service.get_available_slots(
        doctor_id=request.doctor_id,
        date=request.date,
        appointment_type_id=request.appointment_type_id,
    )
    return [
        {"start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in slots
    ]


@router.put("/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: UUID,
    request: RescheduleRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    service = AppointmentService(db)
    a = service.reschedule_appointment(appointment_id, request.new_start_datetime)
    return _appointment_response(a)


@router.put("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    service = AppointmentService(db)
    a = service.cancel_appointment(appointment_id)
    return _appointment_response(a)


@router.put("/{appointment_id}/complete")
def complete_appointment(
    appointment_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    """Mark appointment as completed. Staff/Doctor only."""
    service = AppointmentService(db)
    a = service.complete_appointment(appointment_id)
    return _appointment_response(a)


@router.put("/{appointment_id}/no-show")
def mark_no_show(
    appointment_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    """Mark appointment as no-show. Staff/Doctor only."""
    service = AppointmentService(db)
    a = service.mark_no_show(appointment_id)
    return _appointment_response(a)
