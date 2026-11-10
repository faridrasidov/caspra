from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, exists, func, or_, select

from app.core.domain_errors import ValidationError
from app.models.catalog.arcade import Machine, PlaySession
from app.models.device.device import Device
from app.models.device.management import DeviceOutage
from app.models.ledger.hold import OfflineTransaction
from app.models.ledger.operations import FinancialControl, ReconciliationRun, TransactionAllocation
from app.models.ledger.wallet import LedgerEntry, Refund, Transaction, Wallet
from app.models.tenant.webhook_delivery import WebhookDelivery
from app.schemas.arcade import CurrencyOverview, DailyMetric, MachineReportOut, OverviewOut
from app.services.arcade import ArcadeService
from app.utils.money import currency_exponent


class OverviewService(ArcadeService):
    def _metric(self, code):
        return CurrencyOverview(currency=code, exponent=currency_exponent(code))

    async def _wallets(self, db, tenant_id, currency):
        stmt = (
            select(Wallet.currency, Wallet.type, func.sum(Wallet.balance_minor))
            .where(Wallet.tenant_id == tenant_id, Wallet.type.in_(["credit", "bonus"]))
            .group_by(Wallet.currency, Wallet.type)
        )
        if currency:
            stmt = stmt.where(Wallet.currency == currency)
        totals = {}
        for code, kind, amount in (await db.execute(stmt)).all():
            metric = totals.setdefault(code, self._metric(code))
            setattr(
                metric,
                "paid_balance_minor" if kind == "credit" else "bonus_balance_minor",
                int(amount),
            )
        return totals

    def _day_expression(self, db, zone, start, end):
        if db.get_bind().dialect.name == "postgresql":
            return func.to_char(func.timezone(str(zone), Transaction.created_at), "YYYY-MM-DD")
        windows = []
        value = start
        while value <= end:
            lower = datetime.combine(value, time.min, tzinfo=zone).astimezone(UTC)
            upper = datetime.combine(value + timedelta(days=1), time.min, tzinfo=zone).astimezone(
                UTC
            )
            windows.append(
                (
                    (Transaction.created_at >= lower) & (Transaction.created_at < upper),
                    value.isoformat(),
                )
            )
            value += timedelta(days=1)
        return case(*windows)

    def _filters(self, tenant_id, zone, start, end, currency, location_id):
        filters = [
            Transaction.tenant_id == tenant_id,
            Transaction.status.in_(["posted", "reversed"]),
            Transaction.created_at
            >= datetime.combine(start, time.min, tzinfo=zone).astimezone(UTC),
            Transaction.created_at
            < datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC),
        ]
        if currency:
            filters.append(Transaction.currency == currency)
        if location_id:
            filters.append(Transaction.location_id == location_id)
        return filters

    async def _activity(self, db, tenant_id, zone, start, end, currency, location_id):
        day = self._day_expression(db, zone, start, end)
        filters = self._filters(tenant_id, zone, start, end, currency, location_id)
        stmt = (
            select(
                day,
                Transaction.currency,
                Transaction.type,
                Wallet.type,
                func.sum(Transaction.amount_minor),
            )
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(*filters, Wallet.type.in_(["credit", "bonus"]))
            .group_by(day, Transaction.currency, Transaction.type, Wallet.type)
        )
        totals, daily = {}, {}
        for day_text, code, kind, bucket, amount in (await db.execute(stmt)).all():
            summary = totals.setdefault(code, self._metric(code))
            row = daily.setdefault(
                (day_text, code), DailyMetric(day=date.fromisoformat(day_text), currency=code)
            )
            field = (
                "topup_minor"
                if kind == "credit" and bucket == "credit"
                else "spend_minor"
                if kind in {"debit", "capture"}
                else "refund_minor"
                if kind == "refund"
                else None
            )
            if kind == "credit" and bucket == "bonus":
                summary.bonus_grant_minor += int(amount)
            if field:
                setattr(summary, field, getattr(summary, field) + int(amount))
                setattr(row, field, getattr(row, field) + int(amount))
        await self._funding_breakdown(db, filters, totals)
        return totals, daily

    async def _funding_breakdown(self, db, filters, totals):
        allocated = (
            select(
                Transaction.currency,
                Transaction.type,
                TransactionAllocation.wallet_type,
                func.sum(TransactionAllocation.amount_minor),
            )
            .join(TransactionAllocation, TransactionAllocation.transaction_id == Transaction.id)
            .where(
                *filters,
                TransactionAllocation.tenant_id == Transaction.tenant_id,
                Transaction.type.in_(["debit", "capture", "refund"]),
                TransactionAllocation.wallet_type.in_(["credit", "bonus"]),
            )
            .group_by(Transaction.currency, Transaction.type, TransactionAllocation.wallet_type)
        )
        legacy = (
            select(
                Transaction.currency,
                Transaction.type,
                Wallet.type,
                func.sum(Transaction.amount_minor),
            )
            .join(Wallet, Wallet.id == Transaction.wallet_id)
            .where(
                *filters,
                Transaction.type.in_(["debit", "capture", "refund"]),
                Wallet.type.in_(["credit", "bonus"]),
                ~exists(
                    select(TransactionAllocation.id).where(
                        TransactionAllocation.transaction_id == Transaction.id
                    )
                ),
            )
            .group_by(Transaction.currency, Transaction.type, Wallet.type)
        )
        for stmt in (allocated, legacy):
            for code, kind, bucket, amount in (await db.execute(stmt)).all():
                summary = totals.setdefault(code, self._metric(code))
                prefix = "paid" if bucket == "credit" else "bonus"
                suffix = "refund" if kind == "refund" else "spend"
                field = f"{prefix}_{suffix}_minor"
                setattr(summary, field, getattr(summary, field) + int(amount))
        adjustments = (
            select(
                Transaction.currency,
                func.sum(
                    case(
                        (LedgerEntry.direction == "credit", LedgerEntry.amount_minor),
                        else_=-LedgerEntry.amount_minor,
                    )
                ),
            )
            .join(LedgerEntry, LedgerEntry.transaction_id == Transaction.id)
            .where(*filters, Transaction.type == "adjustment", LedgerEntry.wallet_id.is_not(None))
            .group_by(Transaction.currency)
        )
        for code, amount in (await db.execute(adjustments)).all():
            totals.setdefault(code, self._metric(code)).adjustment_minor = int(amount)
        for metric in totals.values():
            metric.net_spend_minor = metric.spend_minor - metric.refund_minor

    async def _devices(self, db, tenant_id, location_id, now):
        stmt = select(Device.status, Device.last_seen).where(Device.tenant_id == tenant_id)
        if location_id:
            stmt = stmt.where(Device.location_id == location_id)
        counts = {"online": 0, "offline": 0, "unknown": 0, "inactive": 0}
        for status, last_seen in (await db.execute(stmt)).all():
            observed = (
                last_seen.replace(tzinfo=UTC)
                if last_seen and last_seen.tzinfo is None
                else last_seen
            )
            key = (
                "inactive"
                if status != "active"
                else "unknown"
                if observed is None
                else "online"
                if now - observed < timedelta(minutes=3)
                else "offline"
            )
            counts[key] += 1
        return counts

    async def overview(
        self,
        db,
        tenant_id,
        *,
        start: date | None = None,
        end: date | None = None,
        currency=None,
        location_id=None,
    ):
        now = datetime.now(UTC)
        timezone = await self.timezone(db, tenant_id, location_id)
        zone = ZoneInfo(timezone)
        today = now.astimezone(zone).date()
        end = end or today
        start = start or end - timedelta(days=13)
        if end < start or (end - start).days > 365:
            raise ValidationError("Report range must be ordered and at most 366 days")
        totals = await self._wallets(db, tenant_id, currency)
        period, daily = await self._activity(db, tenant_id, zone, start, end, currency, location_id)
        for code, metric in period.items():
            wallet = totals.get(code)
            if wallet:
                metric.paid_balance_minor, metric.bonus_balance_minor = (
                    wallet.paid_balance_minor,
                    wallet.bonus_balance_minor,
                )
            totals[code] = metric
        today_totals, _ = await self._activity(
            db, tenant_id, zone, today, today, currency, location_id
        )
        value = start
        while value <= end:
            for code in totals:
                daily.setdefault((value.isoformat(), code), DailyMetric(day=value, currency=code))
            value += timedelta(days=1)
        run = (
            await db.execute(
                select(ReconciliationRun)
                .where(ReconciliationRun.tenant_id == tenant_id)
                .order_by(ReconciliationRun.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        state = "not_checked"
        if run:
            generated = (
                run.generated_at.replace(tzinfo=UTC)
                if run.generated_at.tzinfo is None
                else run.generated_at
            )
            state = (
                "unhealthy"
                if not run.healthy
                else "healthy"
                if now - generated < timedelta(minutes=10)
                else "stale"
            )
        control = (
            await db.execute(
                select(FinancialControl).where(FinancialControl.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        exceptions = {}
        for key, model, condition in (
            ("plays", PlaySession, PlaySession.status == "unknown"),
            ("offline", OfflineTransaction, OfflineTransaction.status == "manual_review"),
            ("webhooks", WebhookDelivery, WebhookDelivery.status.in_(["dead", "failed"])),
        ):
            exceptions[key] = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(model)
                        .where(model.tenant_id == tenant_id, condition)
                    )
                ).scalar_one()
            )
        return OverviewOut(
            generated_at=now,
            timezone=timezone,
            currencies=list(totals.values()),
            today=[today_totals.get(code, self._metric(code)) for code in totals],
            daily=sorted(daily.values(), key=lambda row: (row.day, row.currency)),
            reconciliation=run.report if run else None,
            reconciliation_state=state,
            financial_writes_paused=bool(control and control.paused),
            device_counts=await self._devices(db, tenant_id, location_id, now),
            exceptions=exceptions,
        )

    async def machine_reports(
        self, db, tenant_id, *, start=None, end=None, currency=None, location_id=None
    ):
        zone = ZoneInfo(await self.timezone(db, tenant_id, location_id))
        end = end or datetime.now(UTC).astimezone(zone).date()
        start = start or end - timedelta(days=13)
        if end < start or (end - start).days > 365:
            raise ValidationError("Report range must be ordered and at most 366 days")
        lower = datetime.combine(start, time.min, tzinfo=zone).astimezone(UTC)
        upper = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
        stmt = select(Machine).where(Machine.tenant_id == tenant_id)
        if currency:
            stmt = stmt.where(Machine.currency == currency)
        if location_id:
            stmt = stmt.where(Machine.location_id == location_id)
        machines = list((await db.execute(stmt)).scalars())
        output = {
            machine.id: MachineReportOut(
                machine_id=machine.id, machine_name=machine.name, currency=machine.currency
            )
            for machine in machines
        }
        conditions = [PlaySession.tenant_id == tenant_id, PlaySession.machine_id.in_(output)]
        period = [*conditions, PlaySession.created_at >= lower, PlaySession.created_at < upper]
        plays = (
            select(
                PlaySession.machine_id,
                func.count(),
                func.sum(PlaySession.amount_minor),
                func.sum(case((PlaySession.activation_outcome == "activated", 1), else_=0)),
                func.sum(case((PlaySession.activation_outcome == "failed", 1), else_=0)),
                func.sum(case((PlaySession.status.in_(["authorized", "unknown"]), 1), else_=0)),
            )
            .where(*period)
            .group_by(PlaySession.machine_id)
        )
        for machine_id, attempts, gross, activations, failures, unresolved in (
            await db.execute(plays)
        ).all():
            row = output[machine_id]
            row.attempts, row.gross_spend_minor = attempts, int(gross)
            row.activations, row.failures, row.unresolved = (
                int(activations),
                int(failures),
                int(unresolved),
            )
        funding = (
            select(
                PlaySession.machine_id,
                TransactionAllocation.wallet_type,
                func.sum(TransactionAllocation.amount_minor),
            )
            .join(
                TransactionAllocation,
                TransactionAllocation.transaction_id == PlaySession.transaction_id,
            )
            .where(*period, TransactionAllocation.tenant_id == tenant_id)
            .group_by(PlaySession.machine_id, TransactionAllocation.wallet_type)
        )
        for machine_id, bucket, value in (await db.execute(funding)).all():
            setattr(
                output[machine_id],
                "bonus_spend_minor" if bucket == "bonus" else "paid_spend_minor",
                int(value),
            )
        refunds = (
            select(PlaySession.machine_id, func.sum(Refund.amount_minor))
            .join(Refund, Refund.original_transaction_id == PlaySession.transaction_id)
            .where(
                *conditions,
                Refund.tenant_id == tenant_id,
                Refund.created_at >= lower,
                Refund.created_at < upper,
                Refund.status == "completed",
            )
            .group_by(PlaySession.machine_id)
        )
        for machine_id, value in (await db.execute(refunds)).all():
            output[machine_id].refund_minor = int(value)
        paid_refunds = (
            select(PlaySession.machine_id, func.sum(TransactionAllocation.amount_minor))
            .join(Refund, Refund.original_transaction_id == PlaySession.transaction_id)
            .join(
                TransactionAllocation,
                TransactionAllocation.transaction_id == Refund.refund_transaction_id,
            )
            .where(
                *conditions,
                Refund.tenant_id == tenant_id,
                Refund.created_at >= lower,
                Refund.created_at < upper,
                Refund.status == "completed",
                TransactionAllocation.wallet_type == "credit",
            )
            .group_by(PlaySession.machine_id)
        )
        for row in output.values():
            row.net_paid_spend_minor = row.paid_spend_minor
        for machine_id, value in (await db.execute(paid_refunds)).all():
            output[machine_id].net_paid_spend_minor -= int(value)
        by_device = {machine.device_id: output[machine.id] for machine in machines}
        outages = select(DeviceOutage).where(
            DeviceOutage.tenant_id == tenant_id,
            DeviceOutage.device_id.in_(by_device),
            DeviceOutage.opened_at < upper,
            or_(DeviceOutage.closed_at.is_(None), DeviceOutage.closed_at > lower),
        )
        for outage in (await db.execute(outages)).scalars():
            opened = (
                outage.opened_at.replace(tzinfo=UTC)
                if outage.opened_at.tzinfo is None
                else outage.opened_at
            )
            closed = outage.closed_at or datetime.now(UTC)
            closed = closed.replace(tzinfo=UTC) if closed.tzinfo is None else closed
            by_device[outage.device_id].reader_offline_seconds += max(
                0, int((min(closed, upper) - max(opened, lower)).total_seconds())
            )
        return list(output.values())
