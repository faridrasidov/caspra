import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.session import create_engine, create_session_factory
from app.models.tenant.organization import Organization
from app.services.exports import ExportService
from app.services.operations import OperationsService
from app.workers.celery_app import celery_app


async def _run(reconcile=False):
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    try:
        async with factory() as db:
            tenants = list(
                (
                    await db.execute(select(Organization.id).where(Organization.status == "active"))
                ).scalars()
            )
        for tenant_id in tenants:
            async with factory() as db:
                if reconcile:
                    if db.get_bind().dialect.name == "postgresql":
                        await db.connection(
                            execution_options={"isolation_level": "REPEATABLE READ"}
                        )
                    await OperationsService().reconcile(db, tenant_id)
                else:
                    await OperationsService().maintenance(db, tenant_id)
    finally:
        await engine.dispose()


@celery_app.task(name="caspra.operations.maintenance")
def maintain_operations():
    return asyncio.run(_run())


@celery_app.task(name="caspra.operations.reconcile")
def reconcile_tenants():
    return asyncio.run(_run(reconcile=True))


async def _exports():
    engine = create_engine(settings.database_url)
    try:
        async with create_session_factory(engine)() as db:
            await ExportService().process_due(db)
    finally:
        await engine.dispose()


@celery_app.task(name="caspra.operations.exports")
def export_transactions():
    return asyncio.run(_exports())
