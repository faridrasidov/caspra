from sqlalchemy import select

from app.core.domain_errors import ForbiddenError
from app.models.catalog.arcade import Machine


class DeviceCapabilityService:
    async def assert_legacy_payments(self, db, device):
        bound = (await db.execute(select(Machine.id).where(Machine.device_id == device.id))).first()
        if bound or not device.legacy_payments_enabled:
            raise ForbiddenError(
                "Use the machine play workflow; arbitrary device payments are not enabled"
            )
