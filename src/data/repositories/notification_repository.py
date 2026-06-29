from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, notification: Notification) -> None:
        self.db.add(notification)

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        return (
            self.db.query(Notification)
            .filter(Notification.notification_id == notification_id)
            .first()
        )

    def get_by_appointment(self, appointment_id: UUID) -> list[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.appointment_id == appointment_id)
            .all()
        )

    def get_pending(self) -> list[Notification]:
        return (
            self.db.query(Notification).filter(Notification.status == "PENDING").all()
        )

    def mark_sent(self, notification: Notification) -> None:
        from datetime import datetime

        notification.status = "SENT"
        notification.sent_at = datetime.utcnow()

    def mark_failed(self, notification: Notification) -> None:
        notification.status = "FAILED"

    def delete(self, notification: Notification) -> None:
        self.db.delete(notification)
