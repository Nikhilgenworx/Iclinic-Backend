"""
Twilio Voice Integration — Outbound calls only.

The system calls the patient (outbound). No inbound calls are supported.

Flow:
  1. Frontend POSTs /voice/initiate → Twilio places outbound call to patient
  2. Patient answers → Twilio POSTs /voice/answered (webhook)
  3. Patient speaks → Twilio STT → POSTs /voice/respond
  4. Agent processes in background; /voice/result polls until done
  5. Call ends → /voice/status cleans up

Endpoints:
  POST /voice/initiate     — Frontend triggers outbound call
  POST /voice/answered     — Twilio webhook when patient picks up
  POST /voice/respond      — Receives transcribed speech
  POST /voice/result       — Polling for agent response
  POST /voice/status       — Twilio call status callback
  POST /voice/dial-status  — Post-escalation dial result
"""

import asyncio
import html
import logging
import sys
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

# Ensure Backend/src is on sys.path for control.* imports
_src_dir = str(Path(__file__).resolve().parents[3])
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from src.core.services import voice_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ─── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/answered")
async def handle_call_answered(request: Request):
    """
    Twilio webhook — called when the patient picks up the outbound call.
    Returns a greeting + <Gather> for speech input.
    """
    from control.voice.voice_config import voice_config

    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    # Outbound call: patient is always "To"
    caller_number = form_data.get("To", "") or form_data.get("From", "unknown")

    logger.info(f"[VOICE] Call answered: {caller_number} (CallSid: {call_sid})")

    # Pre-create session from JWT passed in the URL
    jwt_token = request.query_params.get("jwt", "")
    if jwt_token:
        jwt_token = urllib.parse.unquote(jwt_token)
        voice_service.create_session_with_jwt(call_sid, jwt_token)

    # Build greeting using patient name if available
    patient_name = voice_service.get_patient_name_for_caller(call_sid, caller_number)

    if patient_name:
        greeting = (
            f"Hi {patient_name}, this is Maya from iClinic. How can I help you today?"
        )
    else:
        greeting = "Hi there, this is Maya from iClinic. How can I help you today?"

    base_url = voice_config.server_base_url
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{greeting}</Say>
    <Gather input="speech" action="{base_url}/voice/respond" method="POST" speechTimeout="2" language="en-US">
    </Gather>
    <Say voice="Polly.Joanna">I didn't catch that. Goodbye.</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/initiate")
async def initiate_outbound_call(request: Request):
    """
    Frontend triggers an outbound call to the patient's phone.
    Authenticates via JWT, resolves patient phone, places Twilio call.
    """
    from control.voice.voice_config import voice_config
    from jose import JWTError, jwt
    from src.config.settings import settings
    from twilio.rest import Client

    # Authenticate
    token = _extract_token(request)
    if not token:
        return Response(
            content='{"error": "Authentication required"}',
            status_code=401,
            media_type="application/json",
        )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return Response(
            content='{"error": "Invalid or expired token"}',
            status_code=401,
            media_type="application/json",
        )

    body = await request.json()
    phone_number = body.get("phone_number", "").strip()

    # Auto-resolve phone from patient profile if not provided
    if not phone_number:
        phone_number = _resolve_phone_from_profile(payload)

    if not phone_number:
        return Response(
            content='{"error": "phone_number is required and could not be determined from your profile"}',
            status_code=400,
            media_type="application/json",
        )

    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    # Pre-identify patient so /voice/answered can greet by name
    user_id = payload.get("sub") or payload.get("user_id")
    if user_id:
        _preload_patient_identity(user_id, phone_number)

    # Store chat session continuity
    chat_session_id = body.get("session_id", "")
    if chat_session_id:
        voice_service.store_outbound_session_id(phone_number, chat_session_id)
        logger.info(f"[VOICE] Will continue chat session: {chat_session_id}")

    # Place the outbound call
    logger.info(f"[VOICE] Initiating outbound call to {phone_number}")

    try:
        client = Client(voice_config.twilio_account_sid, voice_config.twilio_auth_token)

        # Auto-verify (Twilio trial accounts only)
        verification_response = _check_verification(client, phone_number)
        if verification_response:
            return verification_response

        # Call the patient — when they answer, Twilio POSTs to /voice/answered
        encoded_token = urllib.parse.quote(token, safe="")
        call = client.calls.create(
            to=phone_number,
            from_=voice_config.twilio_phone_number,
            url=f"{voice_config.server_base_url}/voice/answered?jwt={encoded_token}",
            method="POST",
            status_callback=f"{voice_config.server_base_url}/voice/status",
            status_callback_method="POST",
            status_callback_event=["completed", "failed", "busy", "no-answer"],
        )

        logger.info(f"[VOICE] Call initiated: SID={call.sid}, to={phone_number}")

        # Store mappings for session resolution
        if user_id:
            voice_service.store_outbound_user_id(call.sid, user_id)
            voice_service.store_outbound_user_id(phone_number, user_id)
        if token:
            voice_service.store_outbound_token(call.sid, token)

        return Response(
            content=f'{{"success": true, "call_sid": "{call.sid}", "to": "{phone_number}"}}',
            status_code=200,
            media_type="application/json",
        )

    except Exception as e:
        logger.error(f"[VOICE] Failed to initiate call: {e}", exc_info=True)
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json",
        )


@router.post("/respond")
async def handle_speech_response(request: Request):
    """Receives transcribed speech, kicks off agent in background, returns polling redirect."""
    from control.voice.voice_config import voice_config

    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    speech_result = form_data.get("SpeechResult", "")
    # Outbound: patient is "To"
    caller_number = form_data.get("To", "") or form_data.get("From", "unknown")

    logger.info(f"[VOICE] Speech: '{speech_result}' (call={call_sid})")

    base_url = voice_config.server_base_url

    if not speech_result:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Sorry, I didn't catch that. Could you say that again?</Say>
    <Gather input="speech" action="{base_url}/voice/respond" method="POST" speechTimeout="2" language="en-US">
    </Gather>
    <Say voice="Polly.Joanna">Goodbye.</Say>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Kick off agent processing in background
    voice_service.mark_processing(call_sid)
    asyncio.create_task(
        voice_service.process_speech(call_sid, caller_number, speech_result)
    )

    # Return pause + redirect for polling
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="2"/>
    <Redirect method="POST">{base_url}/voice/result?CallSid={call_sid}&amp;From={html.escape(caller_number)}</Redirect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/result")
async def handle_result_poll(request: Request):
    """Polling endpoint — returns response when agent is done, or redirects to keep waiting."""
    from control.voice.voice_config import voice_config

    form_data = await request.form()
    call_sid = form_data.get("CallSid", request.query_params.get("CallSid", "unknown"))
    caller_number = form_data.get("From", request.query_params.get("From", "unknown"))

    base_url = voice_config.server_base_url
    pending = voice_service.get_pending_response(call_sid)

    if not pending or pending["status"] == "processing":
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="2"/>
    <Redirect method="POST">{base_url}/voice/result?CallSid={call_sid}&amp;From={html.escape(caller_number)}</Redirect>
</Response>"""
        return Response(content=twiml, media_type="application/xml")

    # Agent done — deliver response
    result = voice_service.pop_pending_response(call_sid)
    response_text = result["response"]
    forward_phone = result.get("forward_phone")
    safe_response = html.escape(response_text)

    if forward_phone:
        from control.voice.voice_config import voice_config as vc

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{safe_response}</Say>
    <Dial callerId="{vc.twilio_phone_number}" timeout="30" action="{base_url}/voice/dial-status?CallSid={call_sid}">
        <Number>{forward_phone}</Number>
    </Dial>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{safe_response}</Say>
    <Gather input="speech" action="{base_url}/voice/respond" method="POST" speechTimeout="2" language="en-US">
    </Gather>
    <Say voice="Polly.Joanna">I didn't hear anything. Call back anytime. Goodbye.</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def handle_call_status(request: Request):
    """Twilio status callback — cleanup when call ends."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    call_status = form_data.get("CallStatus", "unknown")

    logger.info(f"[VOICE] Call status: {call_status} (call={call_sid})")

    if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
        voice_service.close_session(call_sid)

    return Response(content="OK", status_code=200)


@router.post("/dial-status")
async def handle_dial_status(request: Request):
    """Post-escalation dial result — handles staff not answering."""
    from control.voice.voice_config import voice_config

    form_data = await request.form()
    call_sid = form_data.get("CallSid", request.query_params.get("CallSid", "unknown"))
    dial_status = form_data.get("DialCallStatus", "completed")

    logger.info(f"[VOICE] Dial status: {dial_status} (call={call_sid})")

    base_url = voice_config.server_base_url

    if dial_status == "completed":
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Thank you for calling iClinic. Goodbye.</Say>
    <Hangup/>
</Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">I'm sorry, our staff couldn't be reached at the moment. Let me continue assisting you. How can I help?</Say>
    <Gather input="speech" action="{base_url}/voice/respond" method="POST" speechTimeout="2" language="en-US">
    </Gather>
    <Say voice="Polly.Joanna">I didn't hear anything. Call back anytime. Goodbye.</Say>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


# ─── Private Helpers ────────────────────────────────────────────────────────────


def _extract_token(request: Request) -> str | None:
    """Extract JWT from Authorization header or cookie."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:]
    return request.cookies.get("access_token")


def _resolve_phone_from_profile(payload: dict) -> str:
    """Auto-fetch patient phone from their profile."""
    from src.config.database import SessionLocal
    from src.core.services.patient_service import PatientService

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        return ""

    try:
        db = SessionLocal()
        patient_service = PatientService(db)
        patient = patient_service.get_patient_by_user_id(user_id)
        phone = patient.phone if patient else ""
        db.close()
        return phone or ""
    except Exception as e:
        logger.warning(f"[VOICE] Could not auto-fetch phone: {e}")
        return ""


def _preload_patient_identity(user_id: str, phone_number: str):
    """Pre-load patient identity so /voice/answered can greet by name."""
    from src.config.database import SessionLocal
    from src.core.services.patient_service import PatientService

    try:
        db = SessionLocal()
        patient_service = PatientService(db)
        patient = patient_service.get_patient_by_user_id(user_id)

        if patient:
            entities = {
                "caller_phone": phone_number,
                "patient_id": str(patient.patient_id),
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "email": patient.email or "",
            }
            entities["booking_history"] = voice_service.load_booking_history(
                db, patient.patient_id
            )
            voice_service.store_outbound_identity(phone_number, entities)
            logger.info(
                f"[VOICE] Pre-identified patient: {patient.first_name} {patient.last_name}"
            )

        db.close()
    except Exception as e:
        logger.warning(f"[VOICE] Could not pre-identify patient: {e}")


def _check_verification(client, phone_number: str) -> Response | None:
    """Check Twilio verification (trial accounts). Returns Response if verification needed."""
    try:
        existing = client.outgoing_caller_ids.list(phone_number=phone_number)
        if not existing:
            logger.info(
                f"[VOICE] Phone {phone_number} not verified — requesting validation"
            )
            validation = client.validation_requests.create(
                phone_number=phone_number,
                friendly_name="iClinic Patient",
            )
            return Response(
                content=(
                    f'{{"error": "verification_required", '
                    f'"message": "Your phone number needs to be verified first. '
                    f"You will receive a call from Twilio — enter code {validation.validation_code} "
                    f'when prompted. Then try calling again.", '
                    f'"validation_code": "{validation.validation_code}"}}'
                ),
                status_code=202,
                media_type="application/json",
            )
    except Exception as e:
        logger.warning(f"[VOICE] Caller ID check failed (may be paid account): {e}")

    return None
