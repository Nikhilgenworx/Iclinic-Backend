"""
Active Bookings Tool — Fetches all active (non-cancelled) appointments
for the current patient. Used by reschedule/cancel workflows so the agent
can identify which appointment the patient is referring to without asking
for a booking ID.
"""

from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class ActiveBookingsInput(BaseModel):
    patient_id: str = Field(
        description="UUID of the patient whose active bookings to retrieve"
    )


class ActiveBookingsTool(BaseTool):
    name = "active_bookings_tool"

    description = (
        "Fetch all active (BOOKED) appointments for a patient. "
        "Returns appointment details including appointment_id, doctor name, "
        "date/time, and status. Use this to identify which appointment the "
        "patient wants to cancel or reschedule — do NOT ask for booking ID."
    )

    args_schema = ActiveBookingsInput

    def __init__(self, appointment_service, doctor_service=None):
        self.appointment_service = appointment_service
        self.doctor_service = doctor_service

    async def execute(self, patient_id: str):
        from uuid import UUID

        try:
            patient_uuid = UUID(patient_id)
        except ValueError:
            return {"error": f"Invalid patient ID: {patient_id}"}

        # Get all appointments for the patient
        all_appointments = self.appointment_service.get_patient_appointments(
            patient_uuid
        )

        # Filter to only active (BOOKED) appointments
        active = [a for a in all_appointments if a.status == "BOOKED"]

        if not active:
            return {
                "active_bookings": [],
                "message": "No active appointments found for this patient.",
            }

        # Build rich response with doctor names
        bookings = []
        for apt in active:
            doctor_name = "Unknown"
            if apt.doctor:
                doctor_name = apt.doctor.full_name

            bookings.append(
                {
                    "appointment_id": str(apt.appointment_id),
                    "doctor_name": doctor_name,
                    "doctor_id": str(apt.doctor_id),
                    "start_datetime": apt.start_datetime.strftime(
                        "%A, %B %d, %Y at %I:%M %p"
                    ),
                    "start_iso": apt.start_datetime.isoformat(),
                    "end_datetime": apt.end_datetime.strftime("%I:%M %p"),
                    "status": apt.status,
                    "booking_source": apt.booking_source,
                }
            )

        return {
            "active_bookings": bookings,
            "count": len(bookings),
        }
