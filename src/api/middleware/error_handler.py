"""
Global error handler middleware.

Catches all unhandled exceptions and returns structured JSON responses
instead of letting the server crash with a 500 Internal Server Error.
"""

import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from src.core.exceptions import ICLinicError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Catches exceptions that escape route handlers and returns clean JSON.
    Prevents the backend from crashing on unhandled errors.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except ICLinicError as e:
            # Our custom exceptions — return the defined status code
            logger.warning(
                f"[{e.status_code}] {request.method} {request.url.path}: {e.message}"
            )
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.message},
            )

        except OperationalError as e:
            # Database connection lost, timeout, etc.
            logger.error(f"[DB] {request.method} {request.url.path}: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Database temporarily unavailable. Please try again."
                },
            )

        except IntegrityError as e:
            # Unique constraint violation, FK violation, etc.
            logger.warning(f"[DB INTEGRITY] {request.method} {request.url.path}: {e}")
            return JSONResponse(
                status_code=409,
                content={"detail": "Data conflict — this record may already exist."},
            )

        except Exception as e:
            # Catch-all for truly unexpected errors
            logger.error(
                f"[UNHANDLED] {request.method} {request.url.path}: "
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An unexpected error occurred. Please try again later.",
                },
            )
