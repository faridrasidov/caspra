from contextvars import ContextVar
from dataclasses import dataclass, replace
from uuid import UUID

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.audit.audit_log import AuditLog


@dataclass(frozen=True)
class AuditRequestContext:
    method: str
    path: str
    request_id: str
    actor_user_id: UUID | None = None
    tenant_id: UUID | None = None


audit_request_context: ContextVar[AuditRequestContext | None] = ContextVar(
    "audit_request_context",
    default=None,
)


def bind_audit_actor(actor_user_id: UUID, tenant_id: UUID) -> None:
    context = audit_request_context.get()
    if context is not None:
        audit_request_context.set(
            replace(
                context,
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
        )


@event.listens_for(Session, "before_commit")
def append_request_audit_log(session: Session) -> None:
    context = audit_request_context.get()
    if (
        context is None
        or context.actor_user_id is None
        or context.tenant_id is None
        or session.info.get("caspra_request_audit_added")
    ):
        return
    session.info["caspra_request_audit_added"] = True
    session.add(
        AuditLog(
            tenant_id=context.tenant_id,
            actor_user_id=context.actor_user_id,
            action=f"{context.method.lower()}:{context.path}",
            target_type="http_request",
            payload={
                "method": context.method,
                "path": context.path,
                "request_id": context.request_id,
            },
        )
    )
