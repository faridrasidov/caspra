import asyncio

from app.core.config import settings
from app.db.session import create_engine, create_session_factory
from app.services.webhook import WebhookService
from app.workers.celery_app import celery_app


async def _deliver_due() -> int:
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as db:
            return await WebhookService().process_due(db)
    finally:
        await engine.dispose()


@celery_app.task(name="caspra.webhooks.deliver_due")
def deliver_due_webhooks() -> int:
    return asyncio.run(_deliver_due())
