from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.domain_errors import ForbiddenError
from app.models.device.device import Device
from app.models.ledger.hold import Hold
from app.models.ledger.wallet import Customer, Refund, Transaction, Wallet
from app.models.tenant.organization import OrgSettings
from app.models.tenant.venue import SpendingLimit


class AuthorizationEngine:
    async def can_debit(self, db, *, tenant_id, account_id, device_id, amount_minor):
        wallet = (
            await db.execute(
                select(Wallet).where(Wallet.id == account_id, Wallet.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        device = (
            await db.execute(
                select(Device).where(Device.id == device_id, Device.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if (
            wallet is None
            or device is None
            or wallet.status != "active"
            or device.status != "active"
        ):
            return False
        customer = await db.get(Customer, wallet.customer_id)
        reserved = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(Hold.amount_minor), 0)).where(
                        Hold.tenant_id == tenant_id,
                        Hold.wallet_id == wallet.id,
                        Hold.status == "preauth",
                        (Hold.expires_at.is_(None)) | (Hold.expires_at > datetime.now(UTC)),
                    )
                )
            ).scalar_one()
        )
        return bool(
            customer
            and customer.status == "active"
            and amount_minor > 0
            and wallet.balance_minor - reserved >= amount_minor
        )

    async def check_daily_limit(self, db, tenant_id, customer_id, currency, amount, now=None):
        limit = (
            await db.execute(
                select(SpendingLimit).where(
                    SpendingLimit.tenant_id == tenant_id,
                    SpendingLimit.customer_id == customer_id,
                    SpendingLimit.currency == currency,
                )
            )
        ).scalar_one_or_none()
        if limit is None:
            return
        now = now or datetime.now(UTC)
        settings = (
            (await db.execute(select(OrgSettings).where(OrgSettings.tenant_id == tenant_id)))
            .scalars()
            .first()
        )
        timezone = ZoneInfo(settings.timezone if settings else "UTC")
        day = now.astimezone(timezone).date()
        start = datetime.combine(day, time.min, tzinfo=timezone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=timezone).astimezone(UTC)
        filters = [
            Transaction.tenant_id == tenant_id,
            Transaction.customer_id == customer_id,
            Transaction.currency == currency,
            Transaction.type.in_(["debit", "capture"]),
            Transaction.created_at >= start,
            Transaction.created_at < end,
        ]
        spent = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(Transaction.amount_minor), 0)).where(*filters)
                )
            ).scalar_one()
        )
        returned = int(
            (
                await db.execute(
                    select(func.coalesce(func.sum(Refund.amount_minor), 0))
                    .join(Transaction, Refund.original_transaction_id == Transaction.id)
                    .where(Refund.tenant_id == tenant_id, Refund.status == "completed", *filters)
                )
            ).scalar_one()
        )
        if spent - returned + amount > limit.daily_minor:
            raise ForbiddenError("Daily spending limit exceeded")
