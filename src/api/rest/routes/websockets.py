"""
WebSocket endpoint for real-time chat with the iClinic AI Agent.

Protocol:
  Client connects to: ws://host:8000/ws/chat?token=<jwt_access_token>

  Client sends JSON:
    { "type": "message", "content": "Hello doctor..." }
    { "type": "ping" }

  Server sends JSON:
    { "type": "message", "content": "Agent response text" }
    { "type": "error", "content": "Error description" }
    { "type": "pong" }
    { "type": "typing", "content": "processing" }
"""

import logging
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

# Ensure Backend/src is on sys.path so that the `control.*` package
# (which uses bare imports like `from control.config...`) can resolve.
_src_dir = str(Path(__file__).resolve().parents[3])  # Backend/src
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Graph Builder ──────────────────────────────────────────────────────────────

# Cache the LLM instance (expensive to initialize, stateless)
_llm = None


def _get_llm():
    """Lazy-initialize the LLM (reused across connections)."""
    global _llm
    if _llm is None:
        from control.factories.llm_factory import LLMFactory

        _llm = LLMFactory.get_llm()
    return _llm


def _build_graph_for_session(db):
    """Build a graph with a per-connection DB session for proper transactions."""
    from control.factories.llm_factory import LLMFactory
    from control.factories.tool_factory import ToolFactory
    from control.graphs.frontdesk_graph import FrontDeskGraph

    registry = ToolFactory.create_registry(db)
    llm = _get_llm()
    router_llm = LLMFactory.get_router_llm()

    graph = FrontDeskGraph(
        llm=llm,
        tool_registry=registry,
        router_llm=router_llm,
    ).get_graph()

    return graph


# ─── WebSocket Endpoint ─────────────────────────────────────────────────────────


def _resolve_patient_from_token(token: str, db) -> dict:
    """
    Decode the JWT token and look up the patient record by user_id.
    Returns a dict of patient entities to pre-populate in state, or empty dict.
    Also loads the last 5 bookings for context/recommendations.
    """
    if not token:
        return {}

    from jose import JWTError, jwt
    from src.config.settings import settings
    from src.core.services.patient_service import PatientService

    try:
        # Decode token — skip expiry check for WebSocket since the connection
        # is long-lived and the frontend handles token refresh separately.
        # The signature is still validated to prevent tampering.
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError as e:
        logger.warning(
            f"WebSocket token decode failed: {e} — continuing without patient context"
        )
        return {}
    except Exception as e:
        logger.warning(f"WebSocket token unexpected error: {type(e).__name__}: {e}")
        return {}

    user_id = payload.get("sub")
    if not user_id:
        return {}

    # Look up patient by user_id
    patient_service = PatientService(db)
    patient = patient_service.get_patient_by_user_id(user_id)

    if not patient:
        # User exists in auth but has no patient record yet — use email from token
        return {
            "user_id": user_id,
            "email": payload.get("email", ""),
        }

    # Patient found — pre-load all their info
    entities = {
        "user_id": user_id,
        "patient_id": str(patient.patient_id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "phone": patient.phone,
        "email": patient.email or payload.get("email", ""),
    }

    # Load last 5 bookings for recommendations and context
    from src.core.services.appointment_service import AppointmentService

    appointment_service = AppointmentService(db)
    all_appointments = appointment_service.get_patient_appointments(patient.patient_id)

    # Recent 5 (any status) for history/recommendations
    recent_5 = all_appointments[:5]
    if recent_5:
        booking_history = []
        for apt in recent_5:
            doctor_name = apt.doctor.full_name if apt.doctor else "Unknown"
            booking_history.append(
                {
                    "doctor_name": doctor_name,
                    "doctor_id": str(apt.doctor_id),
                    "specialty": apt.doctor.specialization if apt.doctor else "",
                    "date": apt.start_datetime.strftime("%A, %B %d, %Y at %I:%M %p"),
                    "status": apt.status,
                }
            )
        entities["booking_history"] = booking_history

    return entities


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, token: str = Query(default="")):
    """
    WebSocket chat endpoint.

    Each connection gets its own DB session via get_db_session().
    When the connection ends cleanly, the session commits.
    If an error occurs, it rolls back.

    The JWT token is decoded to identify the patient. If found in the DB,
    their details (patient_id, name, phone, email) are pre-loaded into
    the conversation state so the agent doesn't need to ask for them.
    """
    await websocket.accept()

    # Generate a unique session ID for this connection
    session_id = f"ws-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": session_id}}
    first_message = True

    logger.info(f"WebSocket connected: session={session_id}")

    # One DB session per WebSocket connection.
    # Commit happens when the connection closes cleanly (exits `with` block).
    # Rollback happens if an unhandled exception propagates.
    from src.data.clients.postgres_client import get_db_session

    with get_db_session() as db:
        graph = _build_graph_for_session(db)

        # Resolve patient from JWT token at connection time
        patient_entities = _resolve_patient_from_token(token, db)
        if patient_entities.get("patient_id"):
            logger.info(
                f"Patient identified: {patient_entities['first_name']} "
                f"{patient_entities['last_name']} (id={patient_entities['patient_id']})"
            )
        else:
            logger.info("No patient record found for this connection")

        # Initialize Redis session store
        redis_store = None
        try:
            from src.data.clients.redis_client import SessionStore

            redis_store = SessionStore(session_id)
            # Save initial state to Redis
            redis_store.save_state(
                {
                    "session_id": session_id,
                    "patient_id": patient_entities.get("patient_id"),
                    "patient_name": (
                        f"{patient_entities['first_name']} {patient_entities['last_name']}"
                        if patient_entities.get("first_name")
                        else None
                    ),
                    "current_intent": None,
                    "pending_action": None,
                }
            )
        except Exception as e:
            logger.warning(f"Redis unavailable: {e} — session state in-memory only")

        try:
            # Send welcome acknowledgment (include patient name if known)
            welcome_content = "Connected to iClinic AI Assistant"
            await websocket.send_json(
                {
                    "type": "connected",
                    "content": welcome_content,
                    "session_id": session_id,
                    "patient_name": (
                        f"{patient_entities['first_name']} {patient_entities['last_name']}"
                        if patient_entities.get("first_name")
                        else None
                    ),
                }
            )

            # Send an automatic greeting message from the bot
            if patient_entities.get("first_name"):
                greeting = f"Hi {patient_entities['first_name']}, welcome to iClinic. How can I help you today?"
            else:
                greeting = "Hi there, welcome to iClinic. How can I help you today?"

            await websocket.send_json(
                {
                    "type": "message",
                    "content": greeting,
                }
            )

            while True:
                # Receive message from client
                try:
                    data = await websocket.receive_json()
                except Exception as recv_err:
                    logger.error(f"Receive error: {recv_err}")
                    break

                msg_type = data.get("type", "message")

                # Handle ping/pong for keepalive
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue

                content = data.get("content", "").strip()
                if not content:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": "Empty message received.",
                        }
                    )
                    continue

                # Indicate the agent is processing
                await websocket.send_json(
                    {
                        "type": "typing",
                        "content": "processing",
                    }
                )

                # Build invocation payload
                from langchain_core.messages import HumanMessage

                invoke_input = {
                    "session_id": session_id,
                    "messages": [HumanMessage(content=content)],
                }

                if first_message:
                    invoke_input.update(
                        {
                            "active_intents": [],
                            "entities": patient_entities,
                            "current_intent": None,
                            "response": None,
                            "patient_preloaded": bool(
                                patient_entities.get("patient_id")
                            ),
                            # Explicit state fields
                            "patient_id": patient_entities.get("patient_id"),
                            "patient_name": (
                                f"{patient_entities['first_name']} {patient_entities['last_name']}"
                                if patient_entities.get("first_name")
                                else None
                            ),
                            "patient_phone": patient_entities.get("phone"),
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
                    first_message = False

                # Invoke the agent graph
                try:
                    print(f"[WS] Invoking graph for session={session_id}...")
                    result = await graph.ainvoke(invoke_input, config=config)
                    response = (result.get("response") or "").strip()

                    # Don't send empty responses to the user
                    if not response:
                        print("[WS] Empty response from graph — skipping send")
                        continue

                    print(f"[WS] Response: {response[:100]}")

                    await websocket.send_json(
                        {
                            "type": "message",
                            "content": response,
                        }
                    )
                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    print(f"[WS] Agent error: {e}")
                    try:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "content": f"Agent error: {str(e)[:200]}",
                            }
                        )
                    except Exception:
                        break

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: session={session_id}")
        except Exception as e:
            logger.error(f"WebSocket unexpected error: {e}", exc_info=True)
            print(f"[WS] Unexpected error: {e}")

    # `with get_db_session()` exited:
    #   - Clean exit → commit (patient, appointment, unavailability all persisted)
    #   - Exception → rollback (nothing saved)

    # Clean up Redis session state (data is now in DB)
    if redis_store:
        try:
            redis_store.delete()
        except Exception:
            pass

    logger.info(f"DB session closed for: session={session_id}")
