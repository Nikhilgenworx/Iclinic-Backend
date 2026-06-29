from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, audit_log: AuditLog) -> None:
        self.db.add(audit_log)

    def get_by_id(self, audit_id: UUID) -> AuditLog | None:
        return self.db.query(AuditLog).filter(AuditLog.audit_id == audit_id).first()

    def get_by_entity(self, entity_type: str, entity_id: UUID) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
            .all()
        )

    def get_by_actor(self, actor_type: str, actor_id: UUID) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.actor_type == actor_type,
                AuditLog.actor_id == actor_id,
            )
            .order_by(AuditLog.created_at.desc())
            .all()
        )

    def get_recent(self, limit: int = 50) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
