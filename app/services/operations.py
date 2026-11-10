from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select

from app.core.admin_permissions import STAFF_ROLES
from app.core.domain_errors import ConflictError
from app.models.catalog.arcade import PlaySession
from app.models.device.device import Device
from app.models.device.management import DeviceOutage
from app.models.identity.user import Permission, Role, RolePermission
from app.models.ledger.hold import OfflineTransaction
from app.models.ledger.operations import FinancialControl, ReconciliationRun
from app.models.ledger.wallet import LedgerEntry
from app.models.tenant.organization import Organization
from app.models.tenant.venue import OperationalAlert
from app.models.tenant.webhook_delivery import WebhookDelivery
from app.services.arcade import ArcadeService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.ledger import LedgerService
from app.services.reconciliation import ReconciliationService


class OperationsService(ArcadeService):
    async def repair_cache(self, db, actor, payload):
        wallet = await LedgerService(commit=False, allow_paused=True)._get_wallet_locked(
            db, actor.tenant_id, payload.wallet_id, for_refund=True
        )
        expected = int(
            (
                await db.execute(
                    select(
                        func.coalesce(
                            func.sum(
                                case(
                                    (LedgerEntry.direction == "credit", LedgerEntry.amount_minor),
                                    else_=-LedgerEntry.amount_minor,
                                )
                            ),
                            0,
                        )
                    ).where(
                        LedgerEntry.tenant_id == actor.tenant_id, LedgerEntry.wallet_id == wallet.id
                    )
                )
            ).scalar_one()
        )
        if expected < 0:
            raise ConflictError("Ledger balance is negative; preserve history for investigation")
        previous = wallet.balance_minor
        wallet.balance_minor = expected
        await AuditService().record(
            db,
            actor.tenant_id,
            actor.id,
            "wallet.cache_rebuilt",
            "wallet",
            str(wallet.id),
            {"reason": payload.reason, "previous_minor": previous, "derived_minor": expected},
        )
        await db.commit()
        reserved = await LedgerService()._active_hold_total(db, actor.tenant_id, wallet.id)
        return {
            "wallet_id": wallet.id,
            "currency": wallet.currency,
            "balance_minor": expected,
            "reserved_minor": reserved,
            "available_minor": expected - reserved,
        }

    async def visible_alerts(self, db, actor, page, limit, q=None):
        permissions = await AuthService().get_permissions(db, actor)
        filters = [OperationalAlert.active.is_(True)]
        if "reports:read" not in permissions and "plays:read" not in permissions:
            filters.append(OperationalAlert.kind == "device_offline")
        return await self.list_records(
            db, OperationalAlert, actor.tenant_id, page, limit, filters=filters, q=q
        )

    async def roles(self, db):
        # Templates are global immutable permission bundles, not tenant-owned roles.
        output = []
        for name, codes in STAFF_ROLES.items():
            role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
            if role is None:
                role = Role(name=name, is_system=True, description=f"Built-in {name}")
                db.add(role)
                await db.flush()
            elif not role.is_system:
                raise ConflictError(f"Role name {name} conflicts with a custom role")
            for code in sorted(codes):
                permission = (
                    await db.execute(select(Permission).where(Permission.code == code))
                ).scalar_one_or_none()
                if permission is None:
                    permission = Permission(code=code)
                    db.add(permission)
                    await db.flush()
                link = (
                    await db.execute(
                        select(RolePermission.id).where(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id == permission.id,
                        )
                    )
                ).first()
                if not link:
                    db.add(RolePermission(role_id=role.id, permission_id=permission.id))
            output.append({"id": role.id, "name": name, "permissions": sorted(codes)})
        await db.commit()
        return output

    async def reconcile(self, db, tenant_id):
        report = await ReconciliationService().report(db, tenant_id)
        db.add(
            ReconciliationRun(
                tenant_id=tenant_id,
                healthy=report.healthy,
                generated_at=report.generated_at,
                report=report.model_dump(mode="json"),
            )
        )
        if not report.healthy:
            control = (
                await db.execute(
                    select(FinancialControl)
                    .where(FinancialControl.tenant_id == tenant_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if control is None:
                control = FinancialControl(tenant_id=tenant_id)
                db.add(control)
            control.paused = True
            control.reason = "Reconciliation differences require review"
        await db.commit()
        return report

    async def resume_financial_writes(self, db, actor, reason):
        control = (
            await db.execute(
                select(FinancialControl)
                .where(FinancialControl.tenant_id == actor.tenant_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        report = await ReconciliationService().report(db, actor.tenant_id)
        if not report.healthy:
            raise ConflictError("Reconciliation must be healthy before reopening writes")
        if control:
            control.paused = False
            control.reason = reason
        db.add(
            ReconciliationRun(
                tenant_id=actor.tenant_id,
                healthy=True,
                generated_at=report.generated_at,
                report=report.model_dump(mode="json"),
            )
        )
        await AuditService().record(
            db, actor.tenant_id, actor.id, "financial_writes.resumed", payload={"reason": reason}
        )
        await db.commit()
        return report

    async def maintenance(self, db, tenant_id):
        await db.execute(select(Organization).where(Organization.id == tenant_id).with_for_update())
        now = datetime.now(UTC)
        pending = list(
            (
                await db.execute(
                    select(PlaySession)
                    .where(
                        PlaySession.tenant_id == tenant_id,
                        PlaySession.status == "authorized",
                        PlaySession.execute_before < now,
                    )
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for play in pending:
            play.status = "unknown"
            play.activation_outcome = "unknown"
            play.resolution_reason = "Activation acknowledgement was not received"
        desired = {}
        await self._device_outages(db, tenant_id, now, desired)
        for play in (
            await db.execute(
                select(PlaySession).where(
                    PlaySession.tenant_id == tenant_id, PlaySession.status == "unknown"
                )
            )
        ).scalars():
            desired[f"play:{play.id}"] = ("unknown_play", f"Play {play.id} requires outcome review")
        for item in (
            await db.execute(
                select(OfflineTransaction).where(
                    OfflineTransaction.tenant_id == tenant_id,
                    OfflineTransaction.status.in_(["pending", "manual_review"]),
                )
            )
        ).scalars():
            desired[f"offline:{item.id}"] = (
                "offline_review",
                f"Offline operation {item.id} requires recovery or review",
            )
        for delivery in (
            await db.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.tenant_id == tenant_id,
                    WebhookDelivery.status.in_(["dead", "failed"]),
                )
            )
        ).scalars():
            desired[f"webhook:{delivery.id}"] = (
                "webhook_failed",
                f"Webhook event {delivery.id} exhausted delivery",
            )
        control = (
            await db.execute(
                select(FinancialControl).where(FinancialControl.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if control and control.paused:
            desired["financial:paused"] = (
                "financial_paused",
                control.reason or "Financial writes are paused",
            )
        current = {
            alert.key: alert
            for alert in (
                await db.execute(
                    select(OperationalAlert).where(OperationalAlert.tenant_id == tenant_id)
                )
            ).scalars()
        }
        for key, (kind, detail) in desired.items():
            row = current.get(key)
            if row is None:
                row = OperationalAlert(tenant_id=tenant_id, key=key, kind=kind, detail=detail)
                db.add(row)
            row.active = True
            row.resolved_at = None
        for key, row in current.items():
            if key not in desired and row.active:
                row.active = False
                row.resolved_at = now
        await db.commit()

    async def _device_outages(self, db, tenant_id, now, desired):
        devices = list(
            (
                await db.execute(
                    select(Device)
                    .where(Device.tenant_id == tenant_id)
                    .order_by(Device.id)
                    .with_for_update()
                )
            ).scalars()
        )
        open_outages = {
            row.device_id: row
            for row in (
                await db.execute(
                    select(DeviceOutage).where(
                        DeviceOutage.tenant_id == tenant_id, DeviceOutage.closed_at.is_(None)
                    )
                )
            ).scalars()
        }
        for device in devices:
            last = device.last_seen or device.created_at
            last = last.replace(tzinfo=UTC) if last.tzinfo is None else last
            offline = device.status == "active" and now - last > timedelta(minutes=3)
            outage = open_outages.get(device.id)
            if offline:
                desired[f"device:{device.id}"] = (
                    "device_offline",
                    f"{device.name} has no recent heartbeat",
                )
                if outage is None:
                    db.add(
                        DeviceOutage(
                            tenant_id=tenant_id,
                            device_id=device.id,
                            opened_at=last + timedelta(minutes=3),
                        )
                    )
            elif outage is not None:
                outage.closed_at = (
                    max(
                        last,
                        outage.opened_at.replace(tzinfo=UTC)
                        if outage.opened_at.tzinfo is None
                        else outage.opened_at,
                    )
                    if device.status == "active"
                    else now
                )
