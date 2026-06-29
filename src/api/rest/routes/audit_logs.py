from uuid import UUID

from fastapi import APIRouter, Depends
from src.api.rest.dependencies import DBSession, require_role
from src.core.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def _audit_response(a):
    return {
        "audit_id": str(a.audit_id),
        "entity_type": a.entity_type,
        "entity_id": str(a.entity_id),
        "action": a.action,
        "actor_type": a.actor_type,
        "actor_id": str(a.actor_id),
        "old_value": a.old_value,
        "new_value": a.new_value,
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
def get_recent_audit_logs(
    db: DBSession,
    limit: int = 50,
    current_user: dict = Depends(require_role("ADMIN")),
):
    """Get recent audit logs. Admin only."""
    service = AuditLogService(db)
    logs = service.get_recent_logs(limit=limit)
    return [_audit_response(a) for a in logs]


@router.get("/entity/{entity_type}/{entity_id}")
def get_entity_audit_logs(
    entity_type: str,
    entity_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = AuditLogService(db)
    logs = service.get_entity_history(entity_type, entity_id)
    return [_audit_response(a) for a in logs]


@router.get("/actor/{actor_type}/{actor_id}")
def get_actor_audit_logs(
    actor_type: str,
    actor_id: UUID,
    db: DBSession,
    current_user: dict = Depends(require_role("ADMIN")),
):
    service = AuditLogService(db)
    logs = service.get_actor_history(actor_type, actor_id)
    return [_audit_response(a) for a in logs]
