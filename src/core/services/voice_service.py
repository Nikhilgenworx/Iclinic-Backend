"""
Voice Service — manages voice call sessions, patient resolution, and agent invocation.

Extracted from the route layer to follow the service pattern.
The route file (api/rest/routes/voice.py) handles HTTP/Twilio protocol only.
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─── In-memory stores ───────────────────────────────────────────────────────────

# call_sid → { graph, config, first_message, patient_entities, db }
_voice_sessions: dict[str, dict] = {}

# call_sid → { "status": "processing"|"done", "response": str, "forward_phone"?: str }
_pending_responses: dict[str, dict] = {}

# phone_number → { patient_id, first_name, ... }
_outbound_identities: dict[str, dict] = {}

# call_sid → JWT token string
_outbound_tokens: dict[str, str] = {}

# call_sid or phone → user_id
_outbound_user_ids: dict[str, str] = {}

# phone_number → session_id (thread_id)
_outbound_session_ids: dict[str, str] = {}

# ─── LLM singleton ─────────────────────────────────────────────────────────────

_llm = None


def get_llm():
    global _llm
    if _llm is None:
        from control.factories.llm_factory import LLMFactory

        _llm = LLMFactory.get_llm()
    return _llm


# ─── Patient Resolution ────────────────────────────────────────────────────────


def resolve_patient_from_token(token: str, db) -> dict:
    """Decode JWT and resolve patient by user_id."""
    if not token:
        return {}

    from jose import JWTError, jwt
    from src.config.settings import settings
    from src.core.services.patient_service import PatientService

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError as e:
        logger.warning(f"[VOICE] Token decode failed: {e}")
        return {}

    user_id = payload.get("sub")
    if not user_id:
        return {}

    patient_service = PatientService(db)
    patient = patient_service.get_patient_by_user_id(user_id)

    if not patient:
        return {"user_id": user_id, "email": payload.get("email", "")}

    entities = {
        "user_id": user_id,
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone": patient.phone,
        "email": patient.email or payload.get("email", ""),
    }

    entities["booking_history"] = load_booking_history(db, patient.patient_id)
    return entities


def resolve_patient_by_user_id(user_id: str, db) -> dict:
    """Resolve patient entities by user_id."""
    from src.core.services.patient_service import PatientService

    patient_service = PatientService(db)
    patient = patient_service.get_patient_by_user_id(user_id)

    if not patient:
        return {"user_id": user_id}

    entities = {
        "user_id": user_id,
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone": patient.phone,
        "email": patient.email or "",
    }

    entities["booking_history"] = load_booking_history(db, patient.patient_id)
    return entities


def identify_patient_by_phone(phone: str, db) -> dict:
    """Look up patient by phone number with fallback strategies."""
    if not phone or phone == "unknown":
        return {}

    # Check pre-loaded outbound identities
    preloaded = _match_outbound_identity(phone)
    if preloaded:
        logger.info(
            f"[VOICE] Patient pre-identified from outbound call: {preloaded.get('first_name')}"
        )
        return preloaded

    from src.core.services.patient_service import PatientService

    patient_service = PatientService(db)

    # Try direct phone lookup with multiple formats
    patient = patient_service.get_patient_by_phone(phone)

    if not patient:
        stripped = phone.lstrip("+")
        if len(stripped) > 10:
            stripped = stripped[-10:]
        patient = patient_service.get_patient_by_phone(stripped)

    if not patient:
        stripped = phone.lstrip("+")
        if len(stripped) == 10:
            patient = patient_service.get_patient_by_phone(f"+91{stripped}")

    # Last resort: match by last 10 digits using SQL LIKE
    if not patient:
        from src.data.models.postgres.patient import Patient

        stripped = phone.lstrip("+")
        last10 = stripped[-10:] if len(stripped) >= 10 else stripped
        patient = db.query(Patient).filter(Patient.phone.like(f"%{last10}")).first()

    if not patient:
        return {"caller_phone": phone}

    entities = {
        "caller_phone": phone,
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone": patient.phone,
        "email": patient.email or "",
    }

    entities["booking_history"] = load_booking_history(db, patient.patient_id)
    return entities


def _match_outbound_identity(phone: str) -> dict | None:
    """Check if phone matches a pre-loaded outbound identity."""
    preloaded = _outbound_identities.get(phone)
    if preloaded:
        _outbound_identities.pop(phone, None)
        return preloaded

    stripped = phone.lstrip("+")
    last10 = stripped[-10:] if len(stripped) > 10 else stripped

    for stored_phone, identity in list(_outbound_identities.items()):
        stored_stripped = stored_phone.lstrip("+")
        stored_last10 = (
            stored_stripped[-10:] if len(stored_stripped) > 10 else stored_stripped
        )
        if stored_last10 == last10:
            _outbound_identities.pop(stored_phone, None)
            return identity

    return None


def load_booking_history(db, patient_id) -> list[dict]:
    """Load last 5 appointments for a patient."""
    from src.core.services.appointment_service import AppointmentService

    appointment_service = AppointmentService(db)
    all_appointments = appointment_service.get_patient_appointments(patient_id)
    recent_5 = all_appointments[:5]

    if not recent_5:
        return []

    history = []
    for apt in recent_5:
        doctor_name = apt.doctor.full_name if apt.doctor else "Unknown"
        history.append(
            {
                "doctor_name": doctor_name,
                "doctor_id": str(apt.doctor_id),
                "specialty": apt.doctor.specialization if apt.doctor else "",
                "date": apt.start_datetime.strftime("%A, %B %d, %Y at %I:%M %p"),
                "status": apt.status,
            }
        )
    return history


# ─── Session Management ─────────────────────────────────────────────────────────


def get_or_create_session(call_sid: str, caller_number: str) -> dict:
    """Get existing session or create a new one for this call."""
    if call_sid in _voice_sessions:
        return _voice_sessions[call_sid]

    from control.factories.llm_factory import LLMFactory
    from control.factories.tool_factory import ToolFactory
    from control.graphs.frontdesk_graph import FrontDeskGraph
    from src.config.database import SessionLocal

    db = SessionLocal()
    registry = ToolFactory.create_registry(db)
    llm = get_llm()
    router_llm = LLMFactory.get_router_llm()

    graph = FrontDeskGraph(
        llm=llm, tool_registry=registry, router_llm=router_llm
    ).get_graph()

    # Resolve patient identity
    patient_entities = _resolve_patient_for_session(call_sid, caller_number, db)

    # Check if continuing an existing chat session
    thread_id, first_message = _resolve_thread_id(call_sid, caller_number)

    session = {
        "graph": graph,
        "config": {"configurable": {"thread_id": thread_id}},
        "first_message": first_message,
        "patient_entities": patient_entities,
        "db": db,
    }

    _voice_sessions[call_sid] = session
    logger.info(
        f"[VOICE] Session created: call={call_sid}, thread={thread_id}, "
        f"patient={patient_entities.get('first_name', 'unknown')}"
    )
    return session


def create_session_with_jwt(call_sid: str, jwt_token: str) -> dict:
    """Pre-create a session using JWT token (called from /voice/incoming)."""
    from control.factories.llm_factory import LLMFactory
    from control.factories.tool_factory import ToolFactory
    from control.graphs.frontdesk_graph import FrontDeskGraph
    from src.config.database import SessionLocal

    db = SessionLocal()
    registry = ToolFactory.create_registry(db)
    llm = get_llm()
    router_llm = LLMFactory.get_router_llm()
    graph = FrontDeskGraph(
        llm=llm, tool_registry=registry, router_llm=router_llm
    ).get_graph()

    patient_entities = resolve_patient_from_token(jwt_token, db)
    logger.info(
        f"[VOICE] Patient from JWT: patient_id={patient_entities.get('patient_id')}, "
        f"name={patient_entities.get('first_name')}"
    )

    thread_id = f"voice-{call_sid}"
    session = {
        "graph": graph,
        "config": {"configurable": {"thread_id": thread_id}},
        "first_message": True,
        "patient_entities": patient_entities,
        "db": db,
    }
    _voice_sessions[call_sid] = session
    return session


def close_session(call_sid: str):
    """Close DB session and cleanup."""
    session = _voice_sessions.pop(call_sid, None)
    _pending_responses.pop(call_sid, None)
    if session and session.get("db"):
        try:
            session["db"].commit()
            session["db"].close()
        except Exception:
            session["db"].rollback()
            session["db"].close()


def _resolve_patient_for_session(call_sid: str, caller_number: str, db) -> dict:
    """Try all resolution strategies in order."""
    # 1. Stored JWT token
    token = _outbound_tokens.pop(call_sid, None)
    if token:
        entities = resolve_patient_from_token(token, db)
        if entities.get("patient_id"):
            logger.info(
                f"[VOICE] Patient resolved from token: {entities.get('patient_id')}"
            )
            return entities

    # 2. Stored user_id
    user_id = _outbound_user_ids.pop(call_sid, None)
    if not user_id:
        user_id = _outbound_user_ids.pop(caller_number, None)
    if not user_id:
        user_id = _match_user_id_by_phone(caller_number)
    if user_id:
        entities = resolve_patient_by_user_id(user_id, db)
        if entities.get("patient_id"):
            logger.info(
                f"[VOICE] Patient resolved by user_id: {entities.get('patient_id')}"
            )
            return entities

    # 3. Phone lookup
    entities = identify_patient_by_phone(caller_number, db)
    logger.info(f"[VOICE] Patient resolved by phone: {entities.get('patient_id')}")
    return entities


def _match_user_id_by_phone(caller_number: str) -> str | None:
    """Find a stored user_id by matching last 10 digits of phone."""
    caller_stripped = caller_number.lstrip("+")
    last10 = caller_stripped[-10:] if len(caller_stripped) >= 10 else caller_stripped

    for stored_key, stored_uid in list(_outbound_user_ids.items()):
        stored_stripped = stored_key.lstrip("+")
        stored_last10 = (
            stored_stripped[-10:] if len(stored_stripped) >= 10 else stored_stripped
        )
        if stored_last10 == last10:
            _outbound_user_ids.pop(stored_key, None)
            return stored_uid
    return None


def _resolve_thread_id(call_sid: str, caller_number: str) -> tuple[str, bool]:
    """Determine thread_id — reuse chat session if available."""
    caller_stripped = caller_number.lstrip("+")
    caller_last10 = (
        caller_stripped[-10:] if len(caller_stripped) > 10 else caller_stripped
    )

    for stored_phone, sid in list(_outbound_session_ids.items()):
        stored_stripped = stored_phone.lstrip("+")
        stored_last10 = (
            stored_stripped[-10:] if len(stored_stripped) > 10 else stored_stripped
        )
        if stored_last10 == caller_last10:
            _outbound_session_ids.pop(stored_phone, None)
            logger.info(f"[VOICE] Continuing chat session: {sid}")
            return sid, False

    return f"voice-{call_sid}", True


# ─── Agent Invocation ───────────────────────────────────────────────────────────


async def process_speech(call_sid: str, caller_number: str, text: str):
    """Background task: invoke agent and store result for polling."""
    forward_phone = None
    try:
        session = get_or_create_session(call_sid, caller_number)
        response_text, forward_phone = await _invoke_agent(session, text)
        logger.info(f"[VOICE] Agent done: {response_text[:80]}")
    except Exception as e:
        logger.error(f"[VOICE] Background error: {e}", exc_info=True)
        response_text = "I'm sorry, I had trouble processing that. Could you try again?"

    result = {"status": "done", "response": response_text}
    if forward_phone:
        result["forward_phone"] = forward_phone
    _pending_responses[call_sid] = result


async def _invoke_agent(session: dict, user_text: str) -> tuple[str, str | None]:
    """Feed user text to the LangGraph agent and return (response, forward_phone or None)."""
    from langchain_core.messages import HumanMessage

    graph = session["graph"]
    config = session["config"]
    patient_entities = session["patient_entities"]

    invoke_input = {
        "session_id": config["configurable"]["thread_id"],
        "messages": [HumanMessage(content=user_text)],
    }

    if session["first_message"]:
        invoke_input.update(
            {
                "active_intents": [],
                "entities": patient_entities,
                "current_intent": None,
                "response": None,
                "patient_preloaded": bool(patient_entities.get("patient_id")),
                "patient_id": patient_entities.get("patient_id"),
                "patient_name": (
                    f"{patient_entities['first_name']} {patient_entities['last_name']}"
                    if patient_entities.get("first_name")
                    else None
                ),
                "patient_phone": patient_entities.get(
                    "phone", patient_entities.get("caller_phone")
                ),
                "patient_email": patient_entities.get("email"),
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
                "booking_history": patient_entities.get("booking_history"),
            }
        )
        session["first_message"] = False

    try:
        result = await graph.ainvoke(invoke_input, config=config)
        response = result.get("response", "I'm sorry, could you say that again?")

        # Detect escalation
        forward_phone = None
        escalation_phone = os.getenv("ESCALATION_PHONE", "")
        if escalation_phone:
            entities = result.get("entities", {})
            if entities.get("escalated") or entities.get("forward_call"):
                forward_phone = escalation_phone
                response = (
                    "Alright, I'm connecting you to our staff now. One moment please."
                )
                logger.info(
                    f"[VOICE] Escalation detected — forwarding to {forward_phone}"
                )

        return response, forward_phone
    except Exception as e:
        logger.error(f"[VOICE] Agent error: {e}", exc_info=True)
        return "I'm sorry, I had trouble with that. Could you try again?", None


# ─── Helpers for route layer ────────────────────────────────────────────────────


def mark_processing(call_sid: str):
    """Mark a call as currently processing."""
    _pending_responses[call_sid] = {"status": "processing", "response": ""}


def get_pending_response(call_sid: str) -> dict | None:
    """Get pending response for a call (None if not started)."""
    return _pending_responses.get(call_sid)


def pop_pending_response(call_sid: str) -> dict | None:
    """Get and remove pending response."""
    return _pending_responses.pop(call_sid, None)


def store_outbound_identity(phone: str, entities: dict):
    _outbound_identities[phone] = entities


def store_outbound_user_id(key: str, user_id: str):
    _outbound_user_ids[key] = user_id


def store_outbound_token(call_sid: str, token: str):
    _outbound_tokens[call_sid] = token


def store_outbound_session_id(phone: str, session_id: str):
    _outbound_session_ids[phone] = session_id


def get_session(call_sid: str) -> dict | None:
    return _voice_sessions.get(call_sid)


def has_existing_chat_session(caller_number: str) -> bool:
    """Check if a chat session exists for this caller."""
    caller_stripped = caller_number.lstrip("+")
    caller_last10 = (
        caller_stripped[-10:] if len(caller_stripped) > 10 else caller_stripped
    )

    for stored_phone in list(_outbound_session_ids.keys()):
        stored_stripped = stored_phone.lstrip("+")
        stored_last10 = (
            stored_stripped[-10:] if len(stored_stripped) > 10 else stored_stripped
        )
        if stored_last10 == caller_last10:
            return True
    return False


def get_patient_name_for_caller(call_sid: str, caller_number: str) -> str | None:
    """Try to find a patient name for greeting."""
    # Check session
    session = _voice_sessions.get(call_sid)
    if session:
        name = session.get("patient_entities", {}).get("first_name")
        if name:
            return name

    # Check outbound identities
    caller_stripped = caller_number.lstrip("+")
    caller_last10 = (
        caller_stripped[-10:] if len(caller_stripped) > 10 else caller_stripped
    )

    for stored_phone, identity in list(_outbound_identities.items()):
        stored_stripped = stored_phone.lstrip("+")
        stored_last10 = (
            stored_stripped[-10:] if len(stored_stripped) > 10 else stored_stripped
        )
        if stored_last10 == caller_last10:
            return identity.get("first_name")

    return None
