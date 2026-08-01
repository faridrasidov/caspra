# app/core/logging.py

from datetime import UTC, datetime
import json
import logging

from app.core.audit_context import audit_request_context
from app.core.request_context import get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        audit_context = audit_request_context.get()
        if audit_context is not None:
            payload["tenant_id"] = str(audit_context.tenant_id) if audit_context.tenant_id else None
            payload["actor_user_id"] = (
                str(audit_context.actor_user_id) if audit_context.actor_user_id else None
            )
        for field in (
            "http_method",
            "http_path",
            "http_status",
            "duration_ms",
            "transaction_id",
            "device_id",
            "idempotency_outcome",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
