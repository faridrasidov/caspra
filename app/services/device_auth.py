# app/services/device_auth.py

from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.domain_errors import UnauthorizedError
from app.core.security import create_access_token
from app.models.device.device import Device, DeviceConfig, DeviceStatus
from app.models.device.management import (
    DeviceHeartbeat,
    DeviceToken,
    DeviceTokenType,
    HeartbeatStatus,
)
from app.schemas.device_auth import (
    DeviceConfigDownloadOut,
    DeviceHandshakeOut,
    DeviceHandshakeRequest,
    DeviceHeartbeatOut,
    DeviceHeartbeatRequest,
    DeviceTokenOut,
)

DEVICE_REFRESH_TOKEN_EXPIRE_DAYS = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class DeviceAuthService:
    """Bootstrap, token issuance, heartbeat, and config download for devices."""

    async def handshake(
        self, db: AsyncSession, payload: DeviceHandshakeRequest
    ) -> DeviceHandshakeOut:
        """Unauthenticated: report whether a claimed device is registered."""
        device = await db.get(Device, payload.device_id)
        return DeviceHandshakeOut(
            device_id=payload.device_id,
            registered=device is not None and device.status == DeviceStatus.ACTIVE.value,
            hmac_required=True,
            server_time=datetime.now(UTC),
        )

    async def login(self, db: AsyncSession, device: Device) -> DeviceTokenOut:
        """Issue a device-access token (JWT) plus a stored refresh token."""
        return await self._issue_tokens(db, device)

    async def refresh(self, db: AsyncSession, refresh_token: str) -> DeviceTokenOut:
        token_hash = _hash_token(refresh_token)
        stmt = select(DeviceToken).where(
            DeviceToken.token_hash == token_hash,
            DeviceToken.type == DeviceTokenType.REFRESH.value,
        )
        stored = (await db.execute(stmt)).scalars().first()
        if stored is None or stored.revoked:
            raise UnauthorizedError("Invalid or expired refresh token")

        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise UnauthorizedError("Invalid or expired refresh token")

        device = await db.get(Device, stored.device_id)
        if device is None or device.status != DeviceStatus.ACTIVE.value:
            raise UnauthorizedError("Device is not active")

        stored.revoked = True
        return await self._issue_tokens(db, device)

    async def heartbeat(
        self, db: AsyncSession, device: Device, payload: DeviceHeartbeatRequest
    ) -> DeviceHeartbeatOut:
        now = datetime.now(UTC)
        heartbeat = DeviceHeartbeat(
            tenant_id=device.tenant_id,
            device_id=device.id,
            last_seen=now,
            status=payload.status.value,
        )
        db.add(heartbeat)
        await db.commit()
        return DeviceHeartbeatOut(
            device_id=device.id,
            status=HeartbeatStatus(payload.status),
            last_seen=now,
            server_time=now,
        )

    async def get_config(self, db: AsyncSession, device: Device) -> DeviceConfigDownloadOut:
        stmt = select(DeviceConfig).where(
            DeviceConfig.device_id == device.id, DeviceConfig.tenant_id == device.tenant_id
        )
        config = (await db.execute(stmt)).scalars().first()
        return DeviceConfigDownloadOut(
            device_id=device.id, config=config.config if config is not None else {}
        )

    async def _issue_tokens(self, db: AsyncSession, device: Device) -> DeviceTokenOut:
        expires_in = settings.access_token_expire_minutes * 60
        access_token = create_access_token(str(device.id))
        raw_refresh = secrets.token_urlsafe(48)
        db.add(
            DeviceToken(
                tenant_id=device.tenant_id,
                device_id=device.id,
                token_hash=_hash_token(raw_refresh),
                type=DeviceTokenType.REFRESH.value,
                expires_at=datetime.now(UTC) + timedelta(days=DEVICE_REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        await db.commit()
        return DeviceTokenOut(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=expires_in,
        )
