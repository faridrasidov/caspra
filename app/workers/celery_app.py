from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "caspra",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks.webhooks", "app.workers.tasks.operations"],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    beat_schedule={
        "prepare-transaction-exports": {"task": "caspra.operations.exports", "schedule": 5.0},
        "maintain-venue-operations": {"task": "caspra.operations.maintenance", "schedule": 30.0},
        "reconcile-tenant-ledgers": {"task": "caspra.operations.reconcile", "schedule": 300.0},
        "deliver-webhook-outbox": {
            "task": "caspra.webhooks.deliver_due",
            "schedule": 5.0,
        },
    },
)
