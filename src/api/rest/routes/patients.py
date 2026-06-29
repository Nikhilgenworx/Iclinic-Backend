from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from src.api.rest.dependencies import CurrentUser, DBSession, require_role
from src.core.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


def _patient_response(p):
    return {
        "patient_id": str(p.patient_id),
        "user_id": str(p.user_id) if p.user_id else None,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "phone": p.phone,
        "email": p.email,
        "dob": p.dob.isoformat() if p.dob else None,
        "gender": p.gender,
        "created_at": p.created_at.isoformat(),
    }


@router.get("/me")
def get_my_patient_profile(
    current_user: CurrentUser,
    db: DBSession,
):
    """Get the current user's patient profile. Returns 404 if not found."""
    user_id = current_user.get("sub")
    service = PatientService(db)
    patient = service.get_patient_by_user_id(user_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    return _patient_response(patient)


class UpdateMyProfileRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    dob: date | None = None
    gender: str | None = None


@router.put("/me")
def update_my_patient_profile(
    request: UpdateMyProfileRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Update the current user's patient profile (non-key fields)."""
    user_id = current_user.get("sub")
    service = PatientService(db)
    patient = service.get_patient_by_user_id(user_id)
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )
    updated = service.update_patient(
        patient_id=patient.patient_id,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        dob=request.dob,
        gender=request.gender,
    )
    return _patient_response(updated)


@router.get("/check-availability")
def check_availability(
    email: str = None,
    phone: str = None,
    db: DBSession = None,
):
    """
    Pre-validation endpoint for the profile completion form.
    Check if an email or phone is already in use before form submission.
    Returns {available: true/false} for each checked field.
    """
    from src.data.repositories.patient_repository import PatientRepository

    repo = PatientRepository(db)
    result = {}

    if email:
        existing = repo.get_by_email(email)
        result["email_available"] = existing is None or existing.user_id is None

    if phone:
        existing = repo.get_by_phone(phone)
        result["phone_available"] = existing is None or existing.user_id is None

    return result


class CreatePatientRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: str | None = None
    dob: date | None = None
    gender: str | None = None


class CompleteProfileRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    dob: date | None = None
    gender: str | None = None


class UpdatePatientRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    dob: date | None = None
    gender: str | None = None


@router.post("/complete-profile", status_code=201)
def complete_profile(
    request_body: CompleteProfileRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("PATIENT")),
):
    """
    Called after first login when profile_completed=false.
    Creates the patient record linked to the auth user and marks the profile as completed.

    If a patient record with the same email already exists (e.g., created by front desk
    or AI agent before the user registered), it links the existing record to this user
    instead of creating a duplicate.
    """
    from sqlalchemy import text

    user_id = current_user.get("sub")
    email = current_user.get("email")

    service = PatientService(db)

    # Check if patient already exists for this user_id
    existing_by_user = service.get_patient_by_user_id(user_id)
    if existing_by_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already completed",
        )

    # Check if a patient record exists with this email (created before registration)
    from src.data.repositories.patient_repository import PatientRepository

    patient_repo = PatientRepository(db)
    existing_by_email = patient_repo.get_by_email(email) if email else None

    if existing_by_email:
        # Link the existing patient record to this auth user
        if existing_by_email.user_id is None:
            existing_by_email.user_id = UUID(user_id)
            # Update name/phone if provided (the user's own data takes precedence)
            existing_by_email.first_name = request_body.first_name
            existing_by_email.last_name = request_body.last_name
            existing_by_email.phone = request_body.phone
            if request_body.dob:
                existing_by_email.dob = request_body.dob
            if request_body.gender:
                existing_by_email.gender = request_body.gender

            # Mark profile completed
            db.execute(
                text("UPDATE users SET profile_completed = true WHERE id = :uid"),
                {"uid": user_id},
            )
            return _patient_response(existing_by_email)
        elif str(existing_by_email.user_id) == user_id:
            # Same user — profile already exists, just mark as completed
            db.execute(
                text("UPDATE users SET profile_completed = true WHERE id = :uid"),
                {"uid": user_id},
            )
            db.commit()
            return _patient_response(existing_by_email)
        else:
            # Email exists AND is already linked to a different user
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already associated with another account",
            )

    # Check if phone already exists
    existing_by_phone = patient_repo.get_by_phone(request_body.phone)
    if existing_by_phone:
        # Link the existing phone-based record to this user
        if existing_by_phone.user_id is None:
            existing_by_phone.user_id = UUID(user_id)
            existing_by_phone.first_name = request_body.first_name
            existing_by_phone.last_name = request_body.last_name
            existing_by_phone.email = email
            if request_body.dob:
                existing_by_phone.dob = request_body.dob
            if request_body.gender:
                existing_by_phone.gender = request_body.gender

            db.execute(
                text("UPDATE users SET profile_completed = true WHERE id = :uid"),
                {"uid": user_id},
            )
            return _patient_response(existing_by_phone)
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This phone number is already associated with another account",
            )

    # No existing record — create fresh
    patient = service.create_patient(
        first_name=request_body.first_name,
        last_name=request_body.last_name,
        phone=request_body.phone,
        email=email,
        dob=request_body.dob,
        gender=request_body.gender,
        user_id=user_id,
    )

    # Mark profile_completed in the users table
    db.execute(
        text("UPDATE users SET profile_completed = true WHERE id = :uid"),
        {"uid": user_id},
    )

    return _patient_response(patient)


@router.get("")
def get_all_patients(
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    """Get all patients. Staff/Doctor only."""
    service = PatientService(db)
    patients = service.get_all_patients()
    return [_patient_response(p) for p in patients]


@router.get("/{patient_id}")
def get_patient(
    patient_id: UUID,
    db: DBSession,
    current_user: dict = Depends(
        require_role("ADMIN", "FRONT_DESK", "DOCTOR", "PATIENT")
    ),
):
    service = PatientService(db)
    p = service.get_patient(patient_id)
    return _patient_response(p)


@router.post("", status_code=201)
def create_patient(
    request: CreatePatientRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "PATIENT")),
):
    """Create a patient profile."""
    service = PatientService(db)
    p = service.create_patient(
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        email=request.email,
        dob=request.dob,
        gender=request.gender,
    )
    return _patient_response(p)


@router.put("/{patient_id}")
def update_patient(
    patient_id: UUID,
    request: UpdatePatientRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "PATIENT")),
):
    service = PatientService(db)
    p = service.update_patient(
        patient_id=patient_id,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        email=request.email,
        dob=request.dob,
        gender=request.gender,
    )
    return _patient_response(p)


@router.delete("/{patient_id}", status_code=204)
def delete_patient(
    patient_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = PatientService(db)
    service.delete_patient(patient_id)
