"""
iClinic Backend — Custom Exception Hierarchy.

These exceptions are caught by the global error handler middleware
and converted to proper HTTP responses without crashing the server.
"""


class ICLinicError(Exception):
    """Base exception for all iClinic backend errors."""

    def __init__(
        self, message: str = "An unexpected error occurred", status_code: int = 500
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


# ─── Client Errors (4xx) ────────────────────────────────────────────────────────


class NotFoundError(ICLinicError):
    """Resource not found (404)."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(message=detail, status_code=404)


class ConflictError(ICLinicError):
    """Duplicate or conflicting resource (409)."""

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(message=message, status_code=409)


class ValidationError(ICLinicError):
    """Invalid input data (422)."""

    def __init__(self, message: str = "Invalid input"):
        super().__init__(message=message, status_code=422)


class UnauthorizedError(ICLinicError):
    """Authentication required or invalid credentials (401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=401)


class ForbiddenError(ICLinicError):
    """Insufficient permissions (403)."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=403)


# ─── External Service Errors (5xx but non-fatal) ────────────────────────────────


class ExternalServiceError(ICLinicError):
    """Third-party service failure (Twilio, LLM, SMTP, etc.)."""

    def __init__(self, service: str, message: str = ""):
        detail = f"External service error: {service}"
        if message:
            detail = f"{service} error: {message}"
        super().__init__(message=detail, status_code=502)


class LLMError(ExternalServiceError):
    """LLM provider failure (Groq, OpenRouter, etc.)."""

    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(service="LLM", message=message)


class SMTPError(ExternalServiceError):
    """Email delivery failure."""

    def __init__(self, message: str = "Failed to send email"):
        super().__init__(service="SMTP", message=message)


class TwilioError(ExternalServiceError):
    """Twilio voice/SMS failure."""

    def __init__(self, message: str = "Voice service unavailable"):
        super().__init__(service="Twilio", message=message)


# ─── Database Errors ─────────────────────────────────────────────────────────────


class DatabaseError(ICLinicError):
    """Database connection or query failure."""

    def __init__(self, message: str = "Database error"):
        super().__init__(message=message, status_code=503)


class DatabaseConnectionError(DatabaseError):
    """Cannot connect to database."""

    def __init__(self):
        super().__init__(message="Database connection unavailable")


# ─── Business Logic Errors ───────────────────────────────────────────────────────


class SlotUnavailableError(ICLinicError):
    """Appointment slot already taken."""

    def __init__(self, message: str = "This time slot is no longer available"):
        super().__init__(message=message, status_code=409)


class PatientNotFoundError(NotFoundError):
    """Patient record not found."""

    def __init__(self, identifier: str = ""):
        super().__init__(resource="Patient", identifier=identifier)


class DoctorNotFoundError(NotFoundError):
    """Doctor record not found."""

    def __init__(self, identifier: str = ""):
        super().__init__(resource="Doctor", identifier=identifier)


class AppointmentNotFoundError(NotFoundError):
    """Appointment record not found."""

    def __init__(self, identifier: str = ""):
        super().__init__(resource="Appointment", identifier=identifier)
