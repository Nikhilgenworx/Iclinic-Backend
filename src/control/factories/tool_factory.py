from control.routing.tool_registry import ToolRegistry
from control.tools.active_bookings_tool import ActiveBookingsTool
from control.tools.appointment_tool import AppointmentTool
from control.tools.availability_tool import AvailabilityTool
from control.tools.cancellation_tool import CancellationTool
from control.tools.doctor_tool import DoctorTool
from control.tools.escalation_tool import EscalationTool
from control.tools.patient_tool import PatientTool
from control.tools.reschedule_tool import RescheduleTool
from control.tools.sms_tool import SmsTool
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from src.core.services.appointment_service import AppointmentService
from src.core.services.conversation_service import ConversationService
from src.core.services.doctor_service import DoctorService
from src.core.services.patient_service import PatientService


class ToolFactory:
    """Creates all agent tools wired to real services backed by a DB session."""

    @staticmethod
    def create_registry(db: Session) -> ToolRegistry:
        # Ensure .env is loaded for env vars
        load_dotenv()

        # Initialize services
        doctor_service = DoctorService(db)
        appointment_service = AppointmentService(db)
        patient_service = PatientService(db)
        conversation_service = ConversationService(db)

        # Initialize tools with services
        availability_tool = AvailabilityTool(
            doctor_service=doctor_service,
            appointment_service=appointment_service,
        )

        doctor_tool = DoctorTool(
            doctor_service=doctor_service,
        )

        # SMS tool (uses Twilio — reads from env)
        sms_tool = SmsTool()

        appointment_tool = AppointmentTool(
            appointment_service=appointment_service,
            sms_tool=sms_tool,
        )

        patient_tool = PatientTool(
            patient_service=patient_service,
        )

        reschedule_tool = RescheduleTool(
            appointment_service=appointment_service,
            sms_tool=sms_tool,
        )

        cancellation_tool = CancellationTool(
            appointment_service=appointment_service,
            sms_tool=sms_tool,
        )

        escalation_tool = EscalationTool(
            conversation_service=conversation_service,
        )

        active_bookings_tool = ActiveBookingsTool(
            appointment_service=appointment_service,
            doctor_service=doctor_service,
        )

        # Build registry
        registry = ToolRegistry(
            appointment_tool=appointment_tool,
            availability_tool=availability_tool,
            doctor_tool=doctor_tool,
            patient_tool=patient_tool,
            reschedule_tool=reschedule_tool,
            cancellation_tool=cancellation_tool,
            escalation_tool=escalation_tool,
            active_bookings_tool=active_bookings_tool,
        )

        return registry
