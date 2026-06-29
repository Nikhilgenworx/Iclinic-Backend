from datetime import datetime

from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class RescheduleToolInput(BaseModel):
    appointment_id: str = Field(description="UUID of the appointment to reschedule")

    new_start_datetime: str = Field(
        description="New appointment start date and time in ISO format (YYYY-MM-DDTHH:MM:SS)"
    )


class RescheduleTool(BaseTool):
    name = "reschedule_tool"

    description = (
        "Reschedule an existing appointment to a new date/time. "
        "Validates that the new slot is available."
    )

    args_schema = RescheduleToolInput

    def __init__(self, appointment_service, sms_tool=None):
        self.appointment_service = appointment_service
        self.sms_tool = sms_tool

    async def execute(
        self,
        appointment_id: str,
        new_start_datetime: str,
    ):
        from uuid import UUID

        try:
            new_start_dt = datetime.fromisoformat(new_start_datetime)
        except ValueError:
            return {
                "error": f"Invalid datetime format: {new_start_datetime}. Use ISO format."
            }

        try:
            apt_uuid = UUID(appointment_id)
        except ValueError:
            return {"error": f"Invalid appointment ID: {appointment_id}"}

        try:
            appointment = self.appointment_service.reschedule_appointment(
                appointment_id=apt_uuid,
                new_start_datetime=new_start_dt,
            )

            # Lock new slot in Redis (old slot freed automatically via DB)
            try:
                from src.data.clients.redis_client import SessionStore

                new_iso = new_start_dt.strftime("%Y-%m-%dT%H:%M:%S")
                store = SessionStore(f"reschedule-{apt_uuid}")
                store.lock_slot(str(appointment.doctor_id), new_iso)
            except Exception:
                pass

            # Send reschedule SMS
            if self.sms_tool:
                try:
                    self._send_reschedule_sms(appointment, new_start_dt)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"[RESCHEDULE] SMS send failed: {e}"
                    )

            # Commit the reschedule to the database
            self.appointment_service.db.commit()

            return {
                "success": True,
                "appointment_id": str(appointment.appointment_id),
                "new_start_datetime": appointment.start_datetime.isoformat(),
                "new_end_datetime": appointment.end_datetime.isoformat(),
                "status": appointment.status,
                "message": "Appointment rescheduled successfully.",
            }

        except Exception as e:
            self.appointment_service.db.rollback()
            return {
                "success": False,
                "error": str(e.detail) if hasattr(e, "detail") else str(e),
            }

    def _send_reschedule_sms(self, appointment, new_start_dt):
        """Send reschedule notification SMS to the patient."""
        import asyncio

        from src.data.models.postgres.doctor import Doctor
        from src.data.models.postgres.patient import Patient

        db = self.appointment_service.db

        patient = (
            db.query(Patient)
            .filter(Patient.patient_id == appointment.patient_id)
            .first()
        )
        if not patient or not patient.phone:
            return

        doctor = (
            db.query(Doctor).filter(Doctor.doctor_id == appointment.doctor_id).first()
        )
        doctor_name = doctor.full_name if doctor else "Your Doctor"

        patient_name = f"{patient.first_name} {patient.last_name}"
        appointment_date = new_start_dt.strftime("%A, %B %d, %Y at %I:%M %p")

        phone = patient.phone.strip()
        if not phone.startswith("+"):
            phone = f"+91{phone}" if len(phone) == 10 else f"+{phone}"

        coro = self.sms_tool.execute(
            to_phone=phone,
            patient_name=patient_name,
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_id=str(appointment.appointment_id),
            sms_type="reschedule",
        )

        loop = asyncio.get_running_loop()
        loop.create_task(coro)
