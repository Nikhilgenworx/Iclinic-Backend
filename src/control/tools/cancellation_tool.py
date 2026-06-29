from control.tools.base_tool import BaseTool
from pydantic import BaseModel, Field


class CancellationToolInput(BaseModel):
    appointment_id: str = Field(description="UUID of the appointment to cancel")


class CancellationTool(BaseTool):
    name = "cancellation_tool"

    description = "Cancel an existing appointment by appointment ID."

    args_schema = CancellationToolInput

    def __init__(self, appointment_service, sms_tool=None):
        self.appointment_service = appointment_service
        self.sms_tool = sms_tool

    async def execute(self, appointment_id: str):
        from uuid import UUID

        try:
            apt_uuid = UUID(appointment_id)
        except ValueError:
            return {"error": f"Invalid appointment ID: {appointment_id}"}

        try:
            appointment = self.appointment_service.cancel_appointment(
                appointment_id=apt_uuid,
            )

            # Release the slot lock in Redis so it shows as free immediately
            try:
                from src.data.clients.redis_client import SessionStore

                start_iso = appointment.start_datetime.strftime("%Y-%m-%dT%H:%M:%S")
                # Release any pending lock on this slot
                store = SessionStore(f"cancel-{apt_uuid}")
                store.release_slot(str(appointment.doctor_id), start_iso)
            except Exception:
                pass

            # Send cancellation SMS
            if self.sms_tool:
                try:
                    self._send_cancellation_sms(appointment)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        f"[CANCELLATION] SMS send failed: {e}"
                    )

            # Commit the cancellation to the database
            self.appointment_service.db.commit()

            return {
                "success": True,
                "appointment_id": str(appointment.appointment_id),
                "status": appointment.status,
                "message": "Appointment cancelled successfully.",
            }

        except Exception as e:
            self.appointment_service.db.rollback()
            return {
                "success": False,
                "error": str(e.detail) if hasattr(e, "detail") else str(e),
            }

    def _send_cancellation_sms(self, appointment):
        """Send cancellation SMS to the patient."""
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
        appointment_date = appointment.start_datetime.strftime(
            "%A, %B %d, %Y at %I:%M %p"
        )

        phone = patient.phone.strip()
        if not phone.startswith("+"):
            phone = f"+91{phone}" if len(phone) == 10 else f"+{phone}"

        coro = self.sms_tool.execute(
            to_phone=phone,
            patient_name=patient_name,
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            appointment_id=str(appointment.appointment_id),
            sms_type="cancellation",
        )

        loop = asyncio.get_running_loop()
        loop.create_task(coro)
