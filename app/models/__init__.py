# app/models/__init__.py

# Importing every model here ensures they are registered on Base.metadata so that
# Alembic autogenerate can discover all tables.

from app.db.session import Base
from app.models.audit.audit_log import AuditLog
from app.models.catalog.product import Product, ProductCategory
from app.models.device.device import (
    Card,
    Device,
    DeviceConfig,
    DeviceEvent,
    Kiosk,
    KioskLog,
)
from app.models.device.kiosk_topup import (
    KioskTopupSession,
    PaymentMethod,
)
from app.models.device.management import (
    DeviceCommand,
    DeviceHeartbeat,
    DeviceTelemetry,
    DeviceToken,
    Firmware,
    FirmwareUpdate,
)
from app.models.identity.user import (
    ApiKey,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
)
from app.models.ledger.external_topup import ExternalTopupSession
from app.models.ledger.hold import (
    Hold,
    OfflineTransaction,
    TempCardAssignment,
)
from app.models.ledger.wallet import (
    Customer,
    LedgerAccount,
    LedgerEntry,
    Refund,
    Transaction,
    Wallet,
    WalletTransfer,
)
from app.models.tenant.organization import (
    BillingSettings,
    Location,
    Membership,
    Notification,
    OfflinePolicy,
    Organization,
    OrgSettings,
    SecuritySettings,
    Webhook,
)
from app.models.tenant.webhook_delivery import WebhookDelivery

__all__ = [
    "ApiKey",
    "AuditLog",
    "Base",
    "BillingSettings",
    "Card",
    "Customer",
    "Device",
    "DeviceCommand",
    "DeviceConfig",
    "DeviceEvent",
    "DeviceHeartbeat",
    "DeviceTelemetry",
    "DeviceToken",
    "ExternalTopupSession",
    "Firmware",
    "FirmwareUpdate",
    "Hold",
    "Kiosk",
    "KioskLog",
    "KioskTopupSession",
    "LedgerAccount",
    "LedgerEntry",
    "Location",
    "Membership",
    "Notification",
    "OfflinePolicy",
    "OfflineTransaction",
    "OrgSettings",
    "Organization",
    "PaymentMethod",
    "Permission",
    "Product",
    "ProductCategory",
    "RefreshToken",
    "Refund",
    "Role",
    "RolePermission",
    "SecuritySettings",
    "TempCardAssignment",
    "Transaction",
    "User",
    "Wallet",
    "WalletTransfer",
    "Webhook",
    "WebhookDelivery",
]
