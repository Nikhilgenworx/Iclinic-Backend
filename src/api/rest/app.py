import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.middleware.error_handler import ErrorHandlerMiddleware
from src.api.rest.routes.appointment_types import router as appointment_types_router
from src.api.rest.routes.appointments import router as appointments_router
from src.api.rest.routes.audit_logs import router as audit_logs_router
from src.api.rest.routes.conversations import router as conversations_router
from src.api.rest.routes.departments import router as departments_router
from src.api.rest.routes.doctor_unavailability import (
    router as doctor_unavailability_router,
)
from src.api.rest.routes.doctors import router as doctors_router
from src.api.rest.routes.health import router as health_router
from src.api.rest.routes.notifications import router as notifications_router
from src.api.rest.routes.patients import router as patients_router
from src.api.rest.routes.staff import router as staff_router
from src.api.rest.routes.voice import router as voice_router
from src.api.rest.routes.websockets import router as websocket_router

logger = logging.getLogger(__name__)

# Ensure Backend/src is on sys.path for control.* imports
_src_dir = str(Path(__file__).resolve().parents[2])  # Backend/src
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

app = FastAPI(title="iClinic Backend")

# Global error handler — catches all unhandled exceptions, returns JSON instead of crashing
app.add_middleware(ErrorHandlerMiddleware)

# CORS — allow frontend origins with credentials (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Docker/production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health (public)
app.include_router(health_router)

# Protected routes (all require valid JWT cookie)
app.include_router(departments_router)
app.include_router(staff_router)
app.include_router(doctors_router)
app.include_router(patients_router)
app.include_router(appointment_types_router)
app.include_router(appointments_router)
app.include_router(doctor_unavailability_router)
app.include_router(notifications_router)
app.include_router(conversations_router)
app.include_router(audit_logs_router)

# WebSocket (chat with AI agent)
app.include_router(websocket_router)

# Voice (Twilio phone calls with AI agent)
app.include_router(voice_router)


# ─── Startup: Pre-warm the AI agent (LLM + config) ─────────────────────────────


@app.on_event("startup")
async def warmup_agent():
    """
    Pre-initialize the LLM client at server startup so the first WebSocket
    connection doesn't pay the cold-start cost. This makes chats fast from
    the very first message.
    """
    logger.info("[WARMUP] Pre-initializing LLM for AI agent...")
    try:
        # Initialize and cache the LLM instance (same one websockets.py uses)
        from src.api.rest.routes.websockets import _get_llm

        _get_llm()
        logger.info("[WARMUP] LLM initialized successfully — agent is ready.")
    except Exception as e:
        logger.error(f"[WARMUP] Failed to pre-initialize LLM: {e}")
        # Non-fatal — will retry on first WebSocket connection
