from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ConversationState(TypedDict, total=False):
    """
    Explicit conversation state for the iClinic AI Front Desk Agent.

    Every field that matters for disambiguation is a top-level key.
    This makes short replies like "yes", "tomorrow", "the first one"
    unambiguous — the graph always knows what pending context exists.
    """

    # ─── Session ────────────────────────────────────────────────────────────────
    session_id: str

    # ─── Message history (LangGraph accumulator) ────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ─── Routing ────────────────────────────────────────────────────────────────
    current_intent: str | None

    # ─── Patient identity ───────────────────────────────────────────────────────
    patient_id: str | None  # UUID string — set from JWT or patient_tool
    patient_name: str | None  # "First Last" for greeting/context
    patient_phone: str | None
    patient_email: str | None
    patient_preloaded: bool  # True when identified from JWT at connection time

    # ─── Booking flow selections ────────────────────────────────────────────────
    selected_doctor_id: str | None  # UUID of chosen doctor
    selected_doctor_name: str | None  # Human-readable name for prompts
    selected_specialty: str | None  # Specialty being searched
    selected_slot: str | None  # ISO datetime string of chosen slot (start_iso)
    selected_appointment_type_id: str | None  # UUID of chosen appointment type
    selected_appointment_type: str | None  # Name (e.g. "Specialist Consultation")

    # ─── Cancel / Reschedule flow ───────────────────────────────────────────────
    selected_appointment_id: str | None  # UUID of appointment being modified

    # ─── Pending action (what the agent last asked the patient to confirm) ──────
    # Values: "confirm_booking", "confirm_cancel", "confirm_reschedule",
    #         "confirm_appointment_type", "choose_slot", "choose_doctor",
    #         "choose_appointment" (which active booking), None
    pending_action: str | None

    # ─── Available options (for disambiguation of "the first one" etc.) ─────────
    available_slots: list[dict] | None  # Last set of slots shown to patient
    available_doctors: list[dict] | None  # Last set of doctors shown
    active_bookings: list[dict] | None  # Patient's active bookings (for cancel/resched)

    # ─── Booking history (for recommendations) ──────────────────────────────────
    booking_history: list[dict] | None

    # ─── Legacy catch-all (for tool outputs not yet mapped to explicit fields) ──
    entities: dict[str, Any]

    # ─── Final response text ────────────────────────────────────────────────────
    response: str | None
