from uuid import UUID

from sqlalchemy.orm import Session
from src.data.models.postgres.audit_log import AuditLog
from src.data.repositories.audit_log_repository import AuditLogRepository


class AuditLogService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_type: str,
        actor_id: UUID,
        old_value: dict | None = None,
        new_value: dict | None = None,
    ) -> AuditLog:
        audit = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            old_value=old_value,
            new_value=new_value,
        )
        self.audit_repo.add(audit)
        self.db.flush()
        return audit

    def get_entity_history(self, entity_type: str, entity_id: UUID) -> list[AuditLog]:
        return self.audit_repo.get_by_entity(entity_type, entity_id)

    def get_actor_history(self, actor_type: str, actor_id: UUID) -> list[AuditLog]:
        return self.audit_repo.get_by_actor(actor_type, actor_id)

    def get_recent_logs(self, limit: int = 50) -> list[AuditLog]:
        return self.audit_repo.get_recent(limit)
