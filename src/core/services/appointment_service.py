from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.appointment import Appointment
from src.data.repositories.appointment_repository import AppointmentRepository
from src.data.repositories.appointment_type_repository import AppointmentTypeRepository
from src.data.repositories.doctor_repository import DoctorRepository
from src.data.repositories.doctor_unavailability_repository import (
    DoctorUnavailabilityRepository,
)
from src.data.repositories.patient_repository import PatientRepository


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
        self.appointment_type_repo = AppointmentTypeRepository(db)
        self.doctor_repo = DoctorRepository(db)
        self.unavailability_repo = DoctorUnavailabilityRepository(db)
        self.patient_repo = PatientRepository(db)

    def book_appointment(
        self,
        patient_id: UUID,
        doctor_id: UUID,
        appointment_type_id: UUID,
        start_datetime: datetime,
        booking_source: str,
        created_by_actor_type: str,
        created_by_actor_id: UUID,
    ) -> Appointment:
        # Validate patient exists
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )

        # Validate doctor exists and is active
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )
        if not doctor.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is not active",
            )

        # Validate appointment type
        appointment_type = self.appointment_type_repo.get_by_id(appointment_type_id)
        if not appointment_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment type not found",
            )

        # Calculate end time
        duration = timedelta(minutes=appointment_type.default_duration_minutes)
        end_datetime = start_datetime + duration

        # Validate slot is within doctor's working hours
        if (
            start_datetime.time() < doctor.working_start_time
            or end_datetime.time() > doctor.working_end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment time is outside doctor's working hours",
            )

        # Check for conflicts with unavailability
        unavailabilities = self.unavailability_repo.get_by_doctor_and_date_range(
            doctor_id, start_datetime, end_datetime
        )
        if unavailabilities:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is unavailable during this time slot",
            )

        # Check for conflicts with existing appointments
        conflicts = self.appointment_repo.get_by_doctor_and_date_range(
            doctor_id, start_datetime, end_datetime
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time slot is already booked",
            )

        # Create appointment
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_type_id=appointment_type_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            status="BOOKED",
            booking_source=booking_source,
            created_by_actor_type=created_by_actor_type,
            created_by_actor_id=created_by_actor_id,
        )
        self.appointment_repo.add(appointment)
        self.db.flush()

        # Mark doctor as unavailable for this slot
        from src.data.models.postgres.doctor_unavailability import (
            DoctorUnavailability,
        )

        unavailability = DoctorUnavailability(
            doctor_id=doctor_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            reason=f"Appointment: {appointment.appointment_id}",
        )
        self.unavailability_repo.add(unavailability)
        self.db.flush()

        return appointment

    def get_appointment(self, appointment_id: UUID) -> Appointment:
        appointment = self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )
        return appointment

    def get_patient_appointments(self, patient_id: UUID) -> list[Appointment]:
        return self.appointment_repo.get_by_patient(patient_id)

    def get_doctor_appointments(self, doctor_id: UUID) -> list[Appointment]:
        return self.appointment_repo.get_by_doctor(doctor_id)

    def get_doctor_appointments_for_date(
        self, doctor_id: UUID, date: datetime
    ) -> list[Appointment]:
        return self.appointment_repo.get_by_doctor_and_date(doctor_id, date)

    def cancel_appointment(self, appointment_id: UUID) -> Appointment:
        appointment = self.get_appointment(appointment_id)

        if appointment.status == "CANCELLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment is already cancelled",
            )

        if appointment.status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel a completed appointment",
            )

        self.appointment_repo.update_status(appointment, "CANCELLED")

        # Remove the unavailability block so the slot becomes free again
        unavailabilities = self.unavailability_repo.get_by_doctor_and_date_range(
            appointment.doctor_id,
            appointment.start_datetime,
            appointment.end_datetime,
        )
        for u in unavailabilities:
            if (
                u.start_datetime == appointment.start_datetime
                and u.end_datetime == appointment.end_datetime
            ):
                self.unavailability_repo.delete(u)
                break

        return appointment

    def complete_appointment(self, appointment_id: UUID) -> Appointment:
        appointment = self.get_appointment(appointment_id)

        if appointment.status != "BOOKED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot complete appointment with status '{appointment.status}'",
            )

        self.appointment_repo.update_status(appointment, "COMPLETED")
        return appointment

    def mark_no_show(self, appointment_id: UUID) -> Appointment:
        appointment = self.get_appointment(appointment_id)

        if appointment.status != "BOOKED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot mark no-show for appointment with status '{appointment.status}'",
            )

        self.appointment_repo.update_status(appointment, "NO_SHOW")
        return appointment

    def reschedule_appointment(
        self, appointment_id: UUID, new_start_datetime: datetime
    ) -> Appointment:
        appointment = self.get_appointment(appointment_id)

        if appointment.status != "BOOKED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only reschedule booked appointments",
            )

        # Get appointment type for duration
        appointment_type = self.appointment_type_repo.get_by_id(
            appointment.appointment_type_id
        )
        duration = timedelta(minutes=appointment_type.default_duration_minutes)
        new_end_datetime = new_start_datetime + duration

        # Get doctor
        doctor = self.doctor_repo.get_by_id(appointment.doctor_id)

        # Validate working hours
        if (
            new_start_datetime.time() < doctor.working_start_time
            or new_end_datetime.time() > doctor.working_end_time
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New time is outside doctor's working hours",
            )

        # Check unavailability (exclude the current appointment's block)
        unavailabilities = self.unavailability_repo.get_by_doctor_and_date_range(
            appointment.doctor_id, new_start_datetime, new_end_datetime
        )
        # Filter out the unavailability that belongs to this appointment
        blocking = [
            u
            for u in unavailabilities
            if not (
                u.start_datetime == appointment.start_datetime
                and u.end_datetime == appointment.end_datetime
            )
        ]
        if blocking:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is unavailable during the new time slot",
            )

        # Check conflicts (exclude current appointment)
        conflicts = self.appointment_repo.get_by_doctor_and_date_range(
            appointment.doctor_id, new_start_datetime, new_end_datetime
        )
        conflicts = [c for c in conflicts if c.appointment_id != appointment_id]
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="New time slot is already booked",
            )

        # Remove old unavailability block
        old_unavailabilities = self.unavailability_repo.get_by_doctor_and_date_range(
            appointment.doctor_id,
            appointment.start_datetime,
            appointment.end_datetime,
        )
        for u in old_unavailabilities:
            if (
                u.start_datetime == appointment.start_datetime
                and u.end_datetime == appointment.end_datetime
            ):
                self.unavailability_repo.delete(u)
                break

        # Update appointment times
        appointment.start_datetime = new_start_datetime
        appointment.end_datetime = new_end_datetime

        # Add new unavailability block
        from src.data.models.postgres.doctor_unavailability import (
            DoctorUnavailability,
        )

        new_unavailability = DoctorUnavailability(
            doctor_id=appointment.doctor_id,
            start_datetime=new_start_datetime,
            end_datetime=new_end_datetime,
            reason=f"Appointment: {appointment.appointment_id}",
        )
        self.unavailability_repo.add(new_unavailability)
        self.db.flush()

        return appointment

    def get_available_slots(
        self, doctor_id: UUID, date: datetime, appointment_type_id: UUID
    ) -> list[dict]:
        """
        Calculate available slots for a doctor on a given date.

        Availability = Working Hours - Unavailability - Existing Appointments
        """
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )

        appointment_type = self.appointment_type_repo.get_by_id(appointment_type_id)
        if not appointment_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment type not found",
            )

        duration = timedelta(minutes=appointment_type.default_duration_minutes)

        # Build day boundaries
        day_start = date.replace(
            hour=doctor.working_start_time.hour,
            minute=doctor.working_start_time.minute,
            second=0,
            microsecond=0,
        )
        day_end = date.replace(
            hour=doctor.working_end_time.hour,
            minute=doctor.working_end_time.minute,
            second=0,
            microsecond=0,
        )

        # Get blocked periods
        unavailabilities = self.unavailability_repo.get_by_doctor_and_date_range(
            doctor_id, day_start, day_end
        )
        appointments = self.appointment_repo.get_by_doctor_and_date_range(
            doctor_id, day_start, day_end
        )

        # Merge all blocked intervals
        blocked = []
        for u in unavailabilities:
            blocked.append((u.start_datetime, u.end_datetime))
        for a in appointments:
            blocked.append((a.start_datetime, a.end_datetime))

        blocked.sort(key=lambda x: x[0])

        # Generate available slots
        available_slots = []
        current = day_start

        for block_start, block_end in blocked:
            while current + duration <= block_start:
                available_slots.append({"start": current, "end": current + duration})
                current += duration

            if current < block_end:
                current = block_end

        # Fill remaining time after last block
        while current + duration <= day_end:
            available_slots.append({"start": current, "end": current + duration})
            current += duration

        return available_slots
