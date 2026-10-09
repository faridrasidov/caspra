# tests/device/test_device_ops.py

from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest

from app.core.domain_errors import NotFoundError, ValidationError
from app.models.device.device import Device
from app.models.device.management import Firmware, FirmwareUpdateStatus
from app.schemas.device_ops import (
    DeviceCommandAckRequest,
    DeviceSettingsUpdateRequest,
    FirmwareUpdateStatusRequest,
    TelemetryPushRequest,
)
from app.services.device_ops import (
    DeviceFirmwareService,
    DeviceSettingsService,
    DeviceSyncService,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def device(db_session, seeded_device) -> Device:
    return await db_session.get(Device, UUID(seeded_device["device_id"]))


async def _firmware(db_session, device: Device, **overrides) -> Firmware:
    data = {
        "tenant_id": device.tenant_id,
        "version": "1.2.0",
        "target_device_type": device.type,
        "binary_url": "https://firmware.example.test/reader/1.2.0.bin?v=1",
        "checksum": "a" * 64,
        "size_bytes": 1024,
    }
    data.update(overrides)
    firmware = Firmware(**data)
    db_session.add(firmware)
    await db_session.commit()
    return firmware


def _status(firmware: Firmware, status: FirmwareUpdateStatus, progress: int = 0, **extra):
    return FirmwareUpdateStatusRequest(
        firmware_id=firmware.id, status=status, progress=progress, **extra
    )


class TestFirmware:
    """Firmware checks, signed downloads and the update state machine."""

    async def test_check_reports_latest_active_firmware(self, db_session, device):
        service = DeviceFirmwareService()
        assert (await service.check(db_session, device)).update_available is False

        firmware = await _firmware(db_session, device)
        await _firmware(db_session, device, version="9.9.9", active=False)
        await _firmware(db_session, device, version="8.0.0", target_device_type="kiosk")

        result = await service.check(db_session, device)
        assert result.update_available is True
        assert result.firmware.id == firmware.id

    async def test_download_url_is_signed_for_this_device(self, db_session, device):
        firmware = await _firmware(db_session, device)
        result = await DeviceFirmwareService().download(db_session, device, firmware.id)

        url = urlsplit(result.download_url)
        query = parse_qs(url.query)
        assert url.scheme == "https"
        assert query["v"] == ["1"]
        assert query["caspra_device_id"] == [str(device.id)]
        assert query["caspra_firmware_id"] == [str(firmware.id)]
        assert len(query["caspra_signature"][0]) == 64

    async def test_download_rejects_non_https_artifact(self, db_session, device):
        firmware = await _firmware(db_session, device, binary_url="http://insecure.test/a.bin")
        with pytest.raises(ValidationError, match="HTTPS"):
            await DeviceFirmwareService().download(db_session, device, firmware.id)

    async def test_download_hides_inactive_and_foreign_firmware(
        self, db_session, device, seeded_device_other
    ):
        service = DeviceFirmwareService()
        inactive = await _firmware(db_session, device, active=False)
        other = await db_session.get(Device, UUID(seeded_device_other["device_id"]))
        foreign = await _firmware(db_session, other)

        for firmware_id in (inactive.id, foreign.id, uuid4()):
            with pytest.raises(NotFoundError, match="Firmware"):
                await service.download(db_session, device, firmware_id)

    async def test_update_walks_through_to_completed(self, db_session, device):
        service = DeviceFirmwareService()
        firmware = await _firmware(db_session, device)
        steps = [
            (FirmwareUpdateStatus.DOWNLOADING, 10),
            (FirmwareUpdateStatus.DOWNLOADING, 60),
            (FirmwareUpdateStatus.INSTALLING, 80),
            (FirmwareUpdateStatus.COMPLETED, 100),
        ]
        for status, progress in steps:
            update = await service.update_status(
                db_session, device, _status(firmware, status, progress)
            )
        assert update.status == "completed"
        assert update.progress == 100

    async def test_update_must_start_as_pending_or_downloading(self, db_session, device):
        firmware = await _firmware(db_session, device)
        with pytest.raises(ValidationError, match="must start"):
            await DeviceFirmwareService().update_status(
                db_session, device, _status(firmware, FirmwareUpdateStatus.INSTALLING, 50)
            )

    async def test_update_cannot_skip_states(self, db_session, device):
        service = DeviceFirmwareService()
        firmware = await _firmware(db_session, device)
        await service.update_status(
            db_session, device, _status(firmware, FirmwareUpdateStatus.PENDING)
        )
        with pytest.raises(ValidationError, match="Invalid firmware transition"):
            await service.update_status(
                db_session, device, _status(firmware, FirmwareUpdateStatus.COMPLETED, 100)
            )

    async def test_progress_cannot_go_backwards(self, db_session, device):
        service = DeviceFirmwareService()
        firmware = await _firmware(db_session, device)
        await service.update_status(
            db_session, device, _status(firmware, FirmwareUpdateStatus.DOWNLOADING, 50)
        )
        with pytest.raises(ValidationError, match="cannot decrease"):
            await service.update_status(
                db_session, device, _status(firmware, FirmwareUpdateStatus.DOWNLOADING, 20)
            )

    async def test_completed_requires_full_progress(self, db_session, device):
        service = DeviceFirmwareService()
        firmware = await _firmware(db_session, device)
        for status, progress in [
            (FirmwareUpdateStatus.DOWNLOADING, 50),
            (FirmwareUpdateStatus.INSTALLING, 90),
        ]:
            await service.update_status(db_session, device, _status(firmware, status, progress))
        with pytest.raises(ValidationError, match="100 percent"):
            await service.update_status(
                db_session, device, _status(firmware, FirmwareUpdateStatus.COMPLETED, 95)
            )

    async def test_failed_is_terminal(self, db_session, device):
        service = DeviceFirmwareService()
        firmware = await _firmware(db_session, device)
        await service.update_status(
            db_session, device, _status(firmware, FirmwareUpdateStatus.DOWNLOADING, 40)
        )
        failed = await service.update_status(
            db_session,
            device,
            _status(firmware, FirmwareUpdateStatus.FAILED, 0, error="checksum mismatch"),
        )
        assert failed.status == "failed"
        with pytest.raises(ValidationError, match="Invalid firmware transition"):
            await service.update_status(
                db_session, device, _status(firmware, FirmwareUpdateStatus.DOWNLOADING, 0)
            )


class TestSettingsAndSync:
    """Device configuration, telemetry, sync status and command acknowledgement."""

    async def test_settings_are_created_then_replaced(self, db_session, device):
        service = DeviceSettingsService()
        assert (await service.get(db_session, device)).config == {}

        await service.update(db_session, device, DeviceSettingsUpdateRequest(config={"beep": True}))
        updated = await service.update(
            db_session, device, DeviceSettingsUpdateRequest(config={"beep": False, "volume": 3})
        )
        assert updated.config == {"beep": False, "volume": 3}
        assert (await service.get(db_session, device)).config == {"beep": False, "volume": 3}

    async def test_reload_command_is_pulled_and_acknowledged(self, db_session, device):
        sync = DeviceSyncService()
        command = await DeviceSettingsService().reload(db_session, device)
        command_id = command.id
        assert (await sync.status(db_session, device)).pending_commands == 1

        pulled = await sync.pull(db_session, device)
        assert [c.id for c in pulled] == [command_id]
        assert pulled[0].status == "leased"
        assert (await sync.status(db_session, device)).pending_commands == 0

        acked = await sync.acknowledge(
            db_session, device, command_id, DeviceCommandAckRequest(status="acked")
        )
        assert acked.status == "acked"
        assert acked.lease_expires_at is None

        again = await sync.acknowledge(
            db_session, device, command_id, DeviceCommandAckRequest(status="acked")
        )
        assert again.status == "acked"

    async def test_failed_ack_requires_error(self, db_session, device):
        sync = DeviceSyncService()
        command = await DeviceSettingsService().reload(db_session, device)
        command_id = command.id
        await sync.pull(db_session, device)

        with pytest.raises(ValidationError, match="requires an error"):
            await sync.acknowledge(
                db_session, device, command_id, DeviceCommandAckRequest(status="failed")
            )

    async def test_unleased_command_cannot_be_acknowledged(self, db_session, device):
        command = await DeviceSettingsService().reload(db_session, device)
        with pytest.raises(ValidationError, match="leased"):
            await DeviceSyncService().acknowledge(
                db_session, device, command.id, DeviceCommandAckRequest(status="acked")
            )

    async def test_other_device_cannot_acknowledge(self, db_session, device, seeded_device_other):
        command = await DeviceSettingsService().reload(db_session, device)
        other = await db_session.get(Device, UUID(seeded_device_other["device_id"]))
        with pytest.raises(NotFoundError, match="Device command"):
            await DeviceSyncService().acknowledge(
                db_session, other, command.id, DeviceCommandAckRequest(status="acked")
            )

    async def test_telemetry_is_stored(self, db_session, device):
        telemetry = await DeviceSyncService().push_telemetry(
            db_session,
            device,
            TelemetryPushRequest(cpu_percent=12.5, temperature_c=41.0, uptime_s=3600),
        )
        assert telemetry.device_id == device.id
        assert telemetry.uptime_s == 3600
