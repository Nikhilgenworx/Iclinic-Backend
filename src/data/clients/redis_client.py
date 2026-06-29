"""
Redis client for session state management.

Provides:
- Connection pool (singleton)
- get_redis() for direct access
- SessionStore class for structured session operations
"""

import json
import logging
from typing import Any

import redis
from src.config.settings import settings

logger = logging.getLogger(__name__)

# ─── Connection Pool (singleton) ────────────────────────────────────────────────

_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


def get_redis() -> redis.Redis:
    """Get a Redis client from the connection pool."""
    return redis.Redis(connection_pool=_get_pool())


# ─── Session Store ──────────────────────────────────────────────────────────────

SESSION_TTL = 3600  # 1 hour sliding TTL
PENDING_BOOKING_TTL = 1800  # 30 minutes for pending booking locks


class SessionStore:
    """
    Redis-backed session store for active conversation state.

    Key schema:
        session:{session_id}           → JSON hash of conversation state
        pending_booking:{doctor_id}:{iso_datetime} → session_id (slot lock)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.key = f"session:{session_id}"
        self.r = get_redis()

    def get_state(self) -> dict[str, Any]:
        """Load full session state from Redis."""
        raw = self.r.get(self.key)
        if raw:
            return json.loads(raw)
        return {}

    def save_state(self, state: dict[str, Any]) -> None:
        """Save session state to Redis with sliding TTL."""
        # Filter out non-serializable values (LangChain messages stay in checkpointer)
        serializable = {}
        for k, v in state.items():
            if k == "messages":
                continue  # Messages handled by LangGraph checkpointer
            try:
                json.dumps(v)
                serializable[k] = v
            except (TypeError, ValueError):
                continue

        self.r.setex(self.key, SESSION_TTL, json.dumps(serializable))

    def update_field(self, field: str, value: Any) -> None:
        """Update a single field in session state."""
        state = self.get_state()
        state[field] = value
        self.save_state(state)

    def delete(self) -> None:
        """Delete session state (on session end)."""
        self.r.delete(self.key)

    # ─── Pending Booking Locks ──────────────────────────────────────────────────

    def lock_slot(self, doctor_id: str, start_iso: str) -> bool:
        """
        Lock a time slot in Redis when a booking is confirmed (before DB commit).
        Returns True if lock acquired, False if slot already locked by another session.
        """
        lock_key = f"pending_booking:{doctor_id}:{start_iso}"
        # SET NX = only set if not exists (atomic)
        acquired = self.r.set(
            lock_key, self.session_id, nx=True, ex=PENDING_BOOKING_TTL
        )
        return bool(acquired)

    def release_slot(self, doctor_id: str, start_iso: str) -> None:
        """Release a slot lock (e.g., on cancellation before commit)."""
        lock_key = f"pending_booking:{doctor_id}:{start_iso}"
        # Only release if we own the lock
        if self.r.get(lock_key) == self.session_id:
            self.r.delete(lock_key)

    @staticmethod
    def is_slot_locked(doctor_id: str, start_iso: str) -> bool:
        """Check if a slot is locked by any session (pending booking)."""
        r = get_redis()
        lock_key = f"pending_booking:{doctor_id}:{start_iso}"
        return r.exists(lock_key) > 0

    @staticmethod
    def get_locked_slots_for_doctor(doctor_id: str) -> list[str]:
        """Get all pending (locked) slot times for a doctor."""
        r = get_redis()
        pattern = f"pending_booking:{doctor_id}:*"
        keys = r.keys(pattern)
        # Extract ISO times from keys
        prefix = f"pending_booking:{doctor_id}:"
        return [k.replace(prefix, "") for k in keys]
