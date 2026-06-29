"""
Interactive Chat with iClinic AI Front Desk Agent.

Run from Backend/src:
    python -m control.chat

Type your messages and chat with the bot.
Type 'quit', 'exit', or 'q' to end the session.
Type 'reset' to start a new conversation.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from control.factories.llm_factory import LLMFactory
from control.graphs.frontdesk_graph import FrontDeskGraph
from control.routing.tool_registry import ToolRegistry
from control.tools.base_tool import BaseTool
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

# ============================================================
# Mock Tools (no DB needed for chat testing)
# ============================================================


class MockAvailabilityInput(BaseModel):
    specialty: str = Field(description="Medical specialty")
    date: str = Field(description="Date in YYYY-MM-DD format")
    appointment_type: str = Field(
        default="General Consultation", description="Appointment type"
    )
    time_preference: str = Field(
        default="", description="Time preference: morning, afternoon, evening"
    )


class MockAvailabilityTool(BaseTool):
    name = "availability_tool"
    description = "Check doctor availability by specialty and date. Returns pre-computed available time slots filtered by time preference."
    args_schema = MockAvailabilityInput

    async def execute(
        self,
        specialty: str,
        date: str,
        appointment_type: str = "General Consultation",
        time_preference: str = "",
    ):
        pref = time_preference.strip().lower()

        if pref == "morning":
            slots_khan = [
                {
                    "start": "09:00 AM",
                    "end": "09:30 AM",
                    "start_iso": "2025-01-20T09:00:00",
                },
                {
                    "start": "09:30 AM",
                    "end": "10:00 AM",
                    "start_iso": "2025-01-20T09:30:00",
                },
                {
                    "start": "10:30 AM",
                    "end": "11:00 AM",
                    "start_iso": "2025-01-20T10:30:00",
                },
                {
                    "start": "11:00 AM",
                    "end": "11:30 AM",
                    "start_iso": "2025-01-20T11:00:00",
                },
            ]
            slots_patel = [
                {
                    "start": "09:00 AM",
                    "end": "09:30 AM",
                    "start_iso": "2025-01-20T09:00:00",
                },
                {
                    "start": "10:00 AM",
                    "end": "10:30 AM",
                    "start_iso": "2025-01-20T10:00:00",
                },
            ]
        elif pref == "afternoon":
            slots_khan = [
                {
                    "start": "12:00 PM",
                    "end": "12:30 PM",
                    "start_iso": "2025-01-20T12:00:00",
                },
                {
                    "start": "01:00 PM",
                    "end": "01:30 PM",
                    "start_iso": "2025-01-20T13:00:00",
                },
                {
                    "start": "02:00 PM",
                    "end": "02:30 PM",
                    "start_iso": "2025-01-20T14:00:00",
                },
            ]
            slots_patel = [
                {
                    "start": "01:00 PM",
                    "end": "01:30 PM",
                    "start_iso": "2025-01-20T13:00:00",
                },
                {
                    "start": "02:30 PM",
                    "end": "03:00 PM",
                    "start_iso": "2025-01-20T14:30:00",
                },
            ]
        elif pref in ("evening", "late afternoon"):
            slots_khan = [
                {
                    "start": "03:00 PM",
                    "end": "03:30 PM",
                    "start_iso": "2025-01-20T15:00:00",
                },
                {
                    "start": "04:00 PM",
                    "end": "04:30 PM",
                    "start_iso": "2025-01-20T16:00:00",
                },
            ]
            slots_patel = [
                {
                    "start": "03:30 PM",
                    "end": "04:00 PM",
                    "start_iso": "2025-01-20T15:30:00",
                },
                {
                    "start": "04:00 PM",
                    "end": "04:30 PM",
                    "start_iso": "2025-01-20T16:00:00",
                },
            ]
        else:
            slots_khan = [
                {
                    "start": "09:30 AM",
                    "end": "10:00 AM",
                    "start_iso": "2025-01-20T09:30:00",
                },
                {
                    "start": "11:00 AM",
                    "end": "11:30 AM",
                    "start_iso": "2025-01-20T11:00:00",
                },
                {
                    "start": "02:00 PM",
                    "end": "02:30 PM",
                    "start_iso": "2025-01-20T14:00:00",
                },
            ]
            slots_patel = [
                {
                    "start": "10:00 AM",
                    "end": "10:30 AM",
                    "start_iso": "2025-01-20T10:00:00",
                },
                {
                    "start": "03:00 PM",
                    "end": "03:30 PM",
                    "start_iso": "2025-01-20T15:00:00",
                },
            ]

        return {
            "specialty": specialty,
            "date": date,
            "date_iso": "2025-01-20",
            "appointment_type": appointment_type,
            "appointment_type_id": "apt-type-001",
            "duration_minutes": 30,
            "available_appointment_types": [
                {
                    "appointment_type_id": "apt-type-001",
                    "name": "General Consultation",
                    "duration_minutes": 15,
                },
                {
                    "appointment_type_id": "apt-type-002",
                    "name": "Specialist Consultation",
                    "duration_minutes": 30,
                },
            ],
            "doctors": [
                {
                    "doctor_id": "doc-001",
                    "doctor_name": "Dr. Sarah Khan",
                    "available_slots": slots_khan,
                    "total_available": len(slots_khan) + 5,
                },
                {
                    "doctor_id": "doc-002",
                    "doctor_name": "Dr. James Patel",
                    "available_slots": slots_patel,
                    "total_available": len(slots_patel) + 3,
                },
            ],
            "instructions": (
                "These are the ONLY available slots. "
                "Present these options to the patient. "
                "NEVER suggest a time that is not in this list. "
                "Use the start_iso value when booking with appointment_tool. "
                "If patient wants more options or a different time, "
                "call this tool again with a different time_preference."
            ),
        }


class MockDoctorInput(BaseModel):
    specialty: str = Field(description="Medical specialty to search for")


class MockDoctorTool(BaseTool):
    name = "doctor_tool"
    description = "Find doctors by specialty."
    args_schema = MockDoctorInput

    async def execute(self, specialty: str):
        return {
            "specialty": specialty,
            "doctors": [
                {
                    "doctor_id": "doc-001",
                    "full_name": "Dr. Sarah Khan",
                    "specialization": specialty.title(),
                    "working_hours": "09:00 AM - 05:00 PM",
                },
                {
                    "doctor_id": "doc-002",
                    "full_name": "Dr. James Patel",
                    "specialization": specialty.title(),
                    "working_hours": "09:00 AM - 05:00 PM",
                },
            ],
        }


class MockPatientInput(BaseModel):
    phone: str = Field(description="Patient phone number")
    first_name: str = Field(default="", description="First name")
    last_name: str = Field(default="", description="Last name")
    email: str = Field(default="", description="Email")


class MockPatientTool(BaseTool):
    name = "patient_tool"
    description = "Look up or create a patient by phone number."
    args_schema = MockPatientInput

    async def execute(
        self, phone: str, first_name: str = "", last_name: str = "", email: str = ""
    ):
        if first_name and last_name:
            return {
                "found": False,
                "created": True,
                "patient_id": "patient-001",
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
            }
        return {
            "found": True,
            "patient_id": "patient-001",
            "first_name": "Nikhil",
            "last_name": "Varma",
            "phone": phone,
        }


class MockAppointmentInput(BaseModel):
    patient_id: str = Field(description="Patient UUID")
    doctor_id: str = Field(description="Doctor UUID")
    appointment_type_id: str = Field(
        default="apt-type-001", description="Appointment type UUID"
    )
    start_datetime: str = Field(description="Start datetime ISO format")
    booking_source: str = Field(default="AI_CHAT", description="Booking source")


class MockAppointmentTool(BaseTool):
    name = "appointment_tool"
    description = "Book an appointment for a patient with a doctor."
    args_schema = MockAppointmentInput

    async def execute(
        self,
        patient_id: str,
        doctor_id: str,
        appointment_type_id: str = "apt-type-001",
        start_datetime: str = "",
        booking_source: str = "AI_CHAT",
    ):
        return {
            "success": True,
            "appointment_id": "apt-12345",
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "start_datetime": start_datetime,
            "status": "BOOKED",
            "booking_source": booking_source,
        }


class MockRescheduleInput(BaseModel):
    appointment_id: str = Field(description="Appointment UUID")
    new_start_datetime: str = Field(description="New start datetime ISO format")


class MockRescheduleTool(BaseTool):
    name = "reschedule_tool"
    description = "Reschedule an existing appointment."
    args_schema = MockRescheduleInput

    async def execute(self, appointment_id: str, new_start_datetime: str):
        return {
            "success": True,
            "appointment_id": appointment_id,
            "new_start_datetime": new_start_datetime,
            "status": "BOOKED",
            "message": "Appointment rescheduled successfully.",
        }


class MockCancellationInput(BaseModel):
    appointment_id: str = Field(description="Appointment UUID")


class MockCancellationTool(BaseTool):
    name = "cancellation_tool"
    description = "Cancel an existing appointment."
    args_schema = MockCancellationInput

    async def execute(self, appointment_id: str):
        return {
            "success": True,
            "appointment_id": appointment_id,
            "status": "CANCELLED",
            "message": "Appointment cancelled successfully.",
        }


class MockEscalationInput(BaseModel):
    reason: str = Field(description="Reason for escalation")
    conversation_id: str = Field(default="", description="Conversation ID")
    patient_phone: str = Field(default="", description="Patient phone")


class MockEscalationTool(BaseTool):
    name = "escalation_tool"
    description = "Escalate to human staff."
    args_schema = MockEscalationInput

    async def execute(
        self, reason: str, conversation_id: str = "", patient_phone: str = ""
    ):
        return {
            "escalated": True,
            "reason": reason,
            "message": "Your request has been escalated. A staff member will assist you shortly.",
        }


class MockActiveBookingsInput(BaseModel):
    patient_id: str = Field(description="Patient UUID")


class MockActiveBookingsTool(BaseTool):
    name = "active_bookings_tool"
    description = "Fetch all active (BOOKED) appointments for a patient."
    args_schema = MockActiveBookingsInput

    async def execute(self, patient_id: str):
        return {
            "active_bookings": [
                {
                    "appointment_id": "apt-12345",
                    "doctor_name": "Dr. Sarah Khan",
                    "doctor_id": "doc-001",
                    "start_datetime": "Monday, January 20, 2025 at 09:30 AM",
                    "start_iso": "2025-01-20T09:30:00",
                    "end_datetime": "10:00 AM",
                    "status": "BOOKED",
                    "booking_source": "AI_CHAT",
                },
            ],
            "count": 1,
        }


# ============================================================
# Chat Loop
# ============================================================


def build_graph():
    """Build the multi-node graph with mock tools."""
    registry = ToolRegistry(
        appointment_tool=MockAppointmentTool(),
        availability_tool=MockAvailabilityTool(),
        doctor_tool=MockDoctorTool(),
        patient_tool=MockPatientTool(),
        reschedule_tool=MockRescheduleTool(),
        cancellation_tool=MockCancellationTool(),
        escalation_tool=MockEscalationTool(),
        active_bookings_tool=MockActiveBookingsTool(),
    )

    print("Initializing LLM...")
    llm = LLMFactory.get_llm()

    print("Building graph...")
    graph = FrontDeskGraph(
        llm=llm,
        tool_registry=registry,
    ).get_graph()

    return graph


async def chat():
    """Interactive chat loop."""
    graph = build_graph()

    session_id = "chat-session-1"
    config = {"configurable": {"thread_id": session_id}}
    first_message = True

    print("\n" + "=" * 60)
    print("  iClinic AI Front Desk Assistant")
    print("  Type your message to chat. Commands:")
    print("    'quit' / 'exit' / 'q'  — end session")
    print("    'reset'                 — start fresh conversation")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\nGoodbye! Have a great day.")
            break

        if user_input.lower() == "reset":
            session_id = f"chat-session-{id(object())}"
            config = {"configurable": {"thread_id": session_id}}
            first_message = True
            print("\n[Session reset. Starting fresh conversation.]\n")
            continue

        # Build invocation payload
        invoke_input = {
            "session_id": session_id,
            "messages": [HumanMessage(content=user_input)],
        }

        # First message needs full state initialization
        if first_message:
            invoke_input.update(
                {
                    "active_intents": [],
                    "entities": {},
                    "current_intent": None,
                    "response": None,
                    "patient_preloaded": False,
                    # Explicit state fields
                    "patient_id": None,
                    "patient_name": None,
                    "patient_phone": None,
                    "patient_email": None,
                    "selected_doctor_id": None,
                    "selected_doctor_name": None,
                    "selected_specialty": None,
                    "selected_slot": None,
                    "selected_appointment_type_id": None,
                    "selected_appointment_type": None,
                    "selected_appointment_id": None,
                    "pending_action": None,
                    "available_slots": None,
                    "available_doctors": None,
                    "active_bookings": None,
                    "booking_history": None,
                }
            )
            first_message = False

        # Invoke the graph
        try:
            result = await graph.ainvoke(invoke_input, config=config)
            response = result.get("response", "I'm sorry, I couldn't process that.")
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"\n[Error: {e}]\n")


def main():
    asyncio.run(chat())


if __name__ == "__main__":
    main()
