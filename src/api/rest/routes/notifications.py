from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api.rest.dependencies import DBSession, require_role
from src.core.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class CreateNotificationRequest(BaseModel):
    appointment_id: UUID
    notification_type: str  # SMS, EMAIL, WHATSAPP


def _notification_response(n):
    return {
        "notification_id": str(n.notification_id),
        "appointment_id": str(n.appointment_id),
        "notification_type": n.notification_type,
        "status": n.status,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "created_at": n.created_at.isoformat(),
    }


@router.get("/pending")
def get_pending_notifications(
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """Get all pending notifications. Staff only."""
    service = NotificationService(db)
    notifications = service.get_pending_notifications()
    return [_notification_response(n) for n in notifications]


@router.get("/appointment/{appointment_id}")
def get_notifications_for_appointment(
    appointment_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK", "DOCTOR")),
):
    service = NotificationService(db)
    notifications = service.get_notifications_for_appointment(appointment_id)
    return [_notification_response(n) for n in notifications]


@router.post("", status_code=201)
def create_notification(
    request: CreateNotificationRequest,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    """Create a notification. Staff only."""
    service = NotificationService(db)
    n = service.create_notification(
        appointment_id=request.appointment_id,
        notification_type=request.notification_type,
    )
    return _notification_response(n)


@router.put("/{notification_id}/sent")
def mark_notification_sent(
    notification_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    service = NotificationService(db)
    n = service.mark_as_sent(notification_id)
    return _notification_response(n)


@router.put("/{notification_id}/failed")
def mark_notification_failed(
    notification_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN", "FRONT_DESK")),
):
    service = NotificationService(db)
    n = service.mark_as_failed(notification_id)
    return _notification_response(n)
