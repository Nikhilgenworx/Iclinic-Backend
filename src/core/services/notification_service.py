from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from src.data.models.postgres.notification import Notification
from src.data.repositories.appointment_repository import AppointmentRepository
from src.data.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_repo = NotificationRepository(db)
        self.appointment_repo = AppointmentRepository(db)

    def create_notification(
        self,
        appointment_id: UUID,
        notification_type: str,
    ) -> Notification:
        # Validate appointment exists
        appointment = self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        notification = Notification(
            appointment_id=appointment_id,
            notification_type=notification_type,
            status="PENDING",
        )
        self.notification_repo.add(notification)
        self.db.flush()
        return notification

    def get_notification(self, notification_id: UUID) -> Notification:
        notification = self.notification_repo.get_by_id(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found",
            )
        return notification

    def get_notifications_for_appointment(
        self, appointment_id: UUID
    ) -> list[Notification]:
        return self.notification_repo.get_by_appointment(appointment_id)

    def get_pending_notifications(self) -> list[Notification]:
        return self.notification_repo.get_pending()

    def mark_as_sent(self, notification_id: UUID) -> Notification:
        notification = self.get_notification(notification_id)
        self.notification_repo.mark_sent(notification)
        return notification

    def mark_as_failed(self, notification_id: UUID) -> Notification:
        notification = self.get_notification(notification_id)
        self.notification_repo.mark_failed(notification)
        return notification
