# app/services/device_ops.py

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import NotFoundError
from app.models.device.device import Device, DeviceConfig, DeviceEvent
from app.models.device.management import (
    DeviceCommand,
    DeviceCommandStatus,
    DeviceCommandType,
    DeviceHeartbeat,
    DeviceTelemetry,
    Firmware,
    FirmwareUpdate,
)
from app.schemas.device_ops import (
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


class DeviceEventService:
    """Device log push and server→device command pull."""

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
        if firmware is None:
            raise NotFoundError("Firmware", str(firmware_id))
        # NOTE: we return a signed-URL-style metadata stub rather than streaming the
        # binary; actual blob delivery is delegated to object storage (see TODO).
        expires_at = datetime.now(UTC) + timedelta(minutes=FIRMWARE_URL_TTL_MINUTES)
        expiry_ts = int(expires_at.timestamp())
        download_url = f"{firmware.binary_url}?device_id={device.id}&expires={expiry_ts}"
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
        update = (await db.execute(stmt)).scalars().first()
        if update is None:
            update = FirmwareUpdate(
                tenant_id=device.tenant_id,
                device_id=device.id,
                firmware_id=payload.firmware_id,
            )
            db.add(update)
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


class DeviceSyncService:
    """Sync status, telemetry push, and command pull for a device."""

    async def status(self, db: AsyncSession, device: Device) -> SyncStatusOut:
        count_stmt = (
            select(func.count())
            .select_from(DeviceCommand)
            .where(
                DeviceCommand.tenant_id == device.tenant_id,
                DeviceCommand.device_id == device.id,
                DeviceCommand.status == DeviceCommandStatus.PENDING.value,
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
            server_time=datetime.now(UTC),
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


async def _pull_pending_commands(db: AsyncSession, device: Device) -> list[DeviceCommand]:
    """Return pending commands for a device and mark them delivered."""
    stmt = (
        select(DeviceCommand)
        .where(
            DeviceCommand.tenant_id == device.tenant_id,
            DeviceCommand.device_id == device.id,
            DeviceCommand.status == DeviceCommandStatus.PENDING.value,
        )
        .order_by(DeviceCommand.created_at.asc())
    )
    commands = list((await db.execute(stmt)).scalars().all())
    for command in commands:
        command.status = DeviceCommandStatus.DELIVERED.value
    if commands:
        await db.commit()
    return commands
