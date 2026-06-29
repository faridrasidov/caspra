# app/engines/authorization.py

from uuid import UUID


class AuthorizationEngine:
    """Decide whether a device/card may debit an account right now."""

    @staticmethod
    async def can_debit(
        *,
        tenant_id: UUID,
        account_id: UUID,
        device_id: str,
        amount_minor: int,
    ) -> bool:
        _ = tenant_id, account_id, device_id, amount_minor
        return False
