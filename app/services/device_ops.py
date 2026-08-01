# app/services/device_ops.py

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.domain_errors import NotFoundError, ValidationError
from app.models.device.device import Device, DeviceConfig, DeviceEvent
from app.models.device.management import (
    DeviceCommand,
    DeviceCommandStatus,
    DeviceCommandType,
    DeviceHeartbeat,
    DeviceTelemetry,
    Firmware,
    FirmwareUpdate,
    FirmwareUpdateStatus,
)
from app.schemas.device_ops import (
    DeviceCommandAckRequest,
    DeviceEventPushRequest,
    DeviceSettingsOut,
    DeviceSettingsUpdateRequest,
    FirmwareCheckOut,
    FirmwareDownloadOut,
    FirmwareInfo,
    FirmwareUpdateStatusRequest,
    SyncStatusOut,
    TelemetryPushRequest,
)

FIRMWARE_URL_TTL_MINUTES = 15
COMMAND_LEASE_MINUTES = 2


class DeviceEventService:
    """Device log push and server-to-device command pull."""

    async def push(self, db: AsyncSession, device: Device, payload: DeviceEventPushRequest) -> int:
        for item in payload.events:
            db.add(
                DeviceEvent(
                    tenant_id=device.tenant_id,
                    device_id=device.id,
                    type=item.type,
                    level=item.level.value,
                    payload=item.payload,
                )
            )
        await db.commit()
        return len(payload.events)

    async def pull(self, db: AsyncSession, device: Device) -> list[DeviceCommand]:
        return await _pull_pending_commands(db, device)


class DeviceSettingsService:
    """Device-facing read/update of its configuration and reload trigger."""

    async def get(self, db: AsyncSession, device: Device) -> DeviceSettingsOut:
        config = await self._get_config(db, device)
        return DeviceSettingsOut(
            device_id=device.id, config=config.config if config is not None else {}
        )

    async def update(
        self, db: AsyncSession, device: Device, payload: DeviceSettingsUpdateRequest
    ) -> DeviceSettingsOut:
        config = await self._get_config(db, device)
        if config is None:
            config = DeviceConfig(
                tenant_id=device.tenant_id, device_id=device.id, config=payload.config
            )
            db.add(config)
        else:
            config.config = payload.config
        await db.commit()
        await db.refresh(config)
        return DeviceSettingsOut(device_id=device.id, config=config.config)

    async def reload(self, db: AsyncSession, device: Device) -> DeviceCommand:
        command = DeviceCommand(
            tenant_id=device.tenant_id,
            device_id=device.id,
            type=DeviceCommandType.RELOAD.value,
            status=DeviceCommandStatus.PENDING.value,
        )
        db.add(command)
        await db.commit()
        await db.refresh(command)
        return command

    async def _get_config(self, db: AsyncSession, device: Device) -> DeviceConfig | None:
        stmt = select(DeviceConfig).where(
            DeviceConfig.device_id == device.id, DeviceConfig.tenant_id == device.tenant_id
        )
        return (await db.execute(stmt)).scalars().first()


class DeviceFirmwareService:
    """Firmware availability check, download metadata, and update reporting."""

    async def check(self, db: AsyncSession, device: Device) -> FirmwareCheckOut:
        firmware = await self._latest_firmware(db, device)
        if firmware is None:
            return FirmwareCheckOut(update_available=False)
        return FirmwareCheckOut(
            update_available=True, firmware=FirmwareInfo.model_validate(firmware)
        )

    async def download(
        self, db: AsyncSession, device: Device, firmware_id: UUID
    ) -> FirmwareDownloadOut:
        stmt = select(Firmware).where(
            Firmware.id == firmware_id, Firmware.tenant_id == device.tenant_id
        )
        firmware = (await db.execute(stmt)).scalars().first()
        if firmware is None or not firmware.active:
            raise NotFoundError("Firmware", str(firmware_id))
        expires_at = datetime.now(UTC) + timedelta(minutes=FIRMWARE_URL_TTL_MINUTES)
        expiry_ts = int(expires_at.timestamp())
        download_url = self._signed_download_url(firmware, device, expiry_ts)
        return FirmwareDownloadOut(
            firmware_id=firmware.id,
            version=firmware.version,
            download_url=download_url,
            checksum=firmware.checksum,
            size_bytes=firmware.size_bytes,
            expires_at=expires_at,
        )

    async def update_status(
        self, db: AsyncSession, device: Device, payload: FirmwareUpdateStatusRequest
    ) -> FirmwareUpdate:
        stmt = select(FirmwareUpdate).where(
            FirmwareUpdate.tenant_id == device.tenant_id,
            FirmwareUpdate.device_id == device.id,
            FirmwareUpdate.firmware_id == payload.firmware_id,
        )
        firmware_stmt = select(Firmware).where(
            Firmware.id == payload.firmware_id,
            Firmware.tenant_id == device.tenant_id,
            Firmware.active.is_(True),
        )
        firmware = (await db.execute(firmware_stmt)).scalars().first()
        if firmware is None:
            raise NotFoundError("Firmware", str(payload.firmware_id))
        update = (await db.execute(stmt)).scalars().first()
        if update is None:
            if payload.status not in {
                FirmwareUpdateStatus.PENDING,
                FirmwareUpdateStatus.DOWNLOADING,
            }:
                raise ValidationError("A firmware update must start as pending or downloading")
            update = FirmwareUpdate(
                tenant_id=device.tenant_id,
                device_id=device.id,
                firmware_id=payload.firmware_id,
            )
            db.add(update)
        else:
            allowed = {
                FirmwareUpdateStatus.PENDING.value: {
                    FirmwareUpdateStatus.DOWNLOADING.value,
                    FirmwareUpdateStatus.FAILED.value,
                },
                FirmwareUpdateStatus.DOWNLOADING.value: {
                    FirmwareUpdateStatus.INSTALLING.value,
                    FirmwareUpdateStatus.FAILED.value,
                },
                FirmwareUpdateStatus.INSTALLING.value: {
                    FirmwareUpdateStatus.COMPLETED.value,
                    FirmwareUpdateStatus.FAILED.value,
                },
                FirmwareUpdateStatus.COMPLETED.value: set(),
                FirmwareUpdateStatus.FAILED.value: set(),
            }
            if (
                payload.status.value != update.status
                and payload.status.value not in allowed[update.status]
            ):
                raise ValidationError(
                    f"Invalid firmware transition: {update.status} -> {payload.status.value}"
                )
        if payload.status == FirmwareUpdateStatus.COMPLETED and payload.progress != 100:
            raise ValidationError("Completed firmware updates must report 100 percent progress")
        if payload.progress < update.progress and payload.status != FirmwareUpdateStatus.FAILED:
            raise ValidationError("Firmware progress cannot decrease")
        update.status = payload.status.value
        update.progress = payload.progress
        update.error = payload.error
        await db.commit()
        await db.refresh(update)
        return update

    async def _latest_firmware(self, db: AsyncSession, device: Device) -> Firmware | None:
        stmt = (
            select(Firmware)
            .where(
                Firmware.tenant_id == device.tenant_id,
                Firmware.target_device_type == device.type,
                Firmware.active.is_(True),
            )
            .order_by(Firmware.created_at.desc())
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _signed_download_url(firmware: Firmware, device: Device, expiry_ts: int) -> str:
        parts = urlsplit(firmware.binary_url)
        if parts.scheme != "https" or not parts.hostname:
            raise ValidationError("Firmware artifacts must use an HTTPS object-storage URL")
        claims = {
            "caspra_checksum": firmware.checksum,
            "caspra_device_id": str(device.id),
            "caspra_expires": str(expiry_ts),
            "caspra_firmware_id": str(firmware.id),
        }
        canonical = "\n".join(
            [
                parts.path,
                claims["caspra_firmware_id"],
                claims["caspra_device_id"],
                claims["caspra_expires"],
                claims["caspra_checksum"],
            ]
        )
        claims["caspra_signature"] = hmac.new(
            settings.firmware_signing_secret.encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()
        query = urlencode([*parse_qsl(parts.query, keep_blank_values=True), *claims.items()])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


class DeviceSyncService:
    """Sync status, telemetry push, and command pull for a device."""

    async def status(self, db: AsyncSession, device: Device) -> SyncStatusOut:
        now = datetime.now(UTC)
        count_stmt = (
            select(func.count())
            .select_from(DeviceCommand)
            .where(
                DeviceCommand.tenant_id == device.tenant_id,
                DeviceCommand.device_id == device.id,
                or_(
                    DeviceCommand.status == DeviceCommandStatus.PENDING.value,
                    and_(
                        DeviceCommand.status == DeviceCommandStatus.LEASED.value,
                        DeviceCommand.lease_expires_at <= now,
                    ),
                ),
            )
        )
        pending = int((await db.execute(count_stmt)).scalar_one())

        hb_stmt = (
            select(DeviceHeartbeat.last_seen)
            .where(
                DeviceHeartbeat.tenant_id == device.tenant_id,
                DeviceHeartbeat.device_id == device.id,
            )
            .order_by(DeviceHeartbeat.last_seen.desc())
            .limit(1)
        )
        last_seen = (await db.execute(hb_stmt)).scalars().first()
        return SyncStatusOut(
            device_id=device.id,
            pending_commands=pending,
            last_seen=last_seen,
            server_time=now,
        )

    async def push_telemetry(
        self, db: AsyncSession, device: Device, payload: TelemetryPushRequest
    ) -> DeviceTelemetry:
        telemetry = DeviceTelemetry(
            tenant_id=device.tenant_id,
            device_id=device.id,
            cpu_percent=payload.cpu_percent,
            temperature_c=payload.temperature_c,
            uptime_s=payload.uptime_s,
        )
        db.add(telemetry)
        await db.commit()
        await db.refresh(telemetry)
        return telemetry

    async def pull(self, db: AsyncSession, device: Device) -> list[DeviceCommand]:
        return await _pull_pending_commands(db, device)

    async def acknowledge(
        self,
        db: AsyncSession,
        device: Device,
        command_id: UUID,
        payload: DeviceCommandAckRequest,
    ) -> DeviceCommand:
        stmt = (
            select(DeviceCommand)
            .where(
                DeviceCommand.id == command_id,
                DeviceCommand.tenant_id == device.tenant_id,
                DeviceCommand.device_id == device.id,
            )
            .with_for_update()
        )
        command = (await db.execute(stmt)).scalars().first()
        if command is None:
            raise NotFoundError("Device command", str(command_id))
        if command.status == payload.status:
            return command
        if command.status != DeviceCommandStatus.LEASED.value:
            raise ValidationError("Only a leased command can be acknowledged")
        if payload.status == DeviceCommandStatus.FAILED.value and not payload.error:
            raise ValidationError("A failed command acknowledgement requires an error")

        command.status = payload.status
        command.acknowledged_at = datetime.now(UTC)
        command.last_error = payload.error
        command.lease_expires_at = None
        await db.commit()
        await db.refresh(command)
        return command


async def _pull_pending_commands(db: AsyncSession, device: Device) -> list[DeviceCommand]:
    """Lease pending or abandoned commands for explicit device acknowledgement."""
    now = datetime.now(UTC)
    stmt = (
        select(DeviceCommand)
        .where(
            DeviceCommand.tenant_id == device.tenant_id,
            DeviceCommand.device_id == device.id,
            or_(
                DeviceCommand.status == DeviceCommandStatus.PENDING.value,
                and_(
                    DeviceCommand.status == DeviceCommandStatus.LEASED.value,
                    DeviceCommand.lease_expires_at <= now,
                ),
            ),
        )
        .order_by(DeviceCommand.created_at.asc())
        .limit(100)
        .with_for_update(skip_locked=True)
    )
    commands = list((await db.execute(stmt)).scalars().all())
    for command in commands:
        command.status = DeviceCommandStatus.LEASED.value
        command.delivered_at = now
        command.lease_expires_at = now + timedelta(minutes=COMMAND_LEASE_MINUTES)
        command.delivery_attempts += 1
    if commands:
        await db.commit()
    return commands
