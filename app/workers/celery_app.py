from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "caspra",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks.webhooks"],
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
        "deliver-webhook-outbox": {
            "task": "caspra.webhooks.deliver_due",
            "schedule": 5.0,
        }
    },
)
