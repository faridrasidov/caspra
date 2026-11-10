# app/models/__init__.py

# Importing every model here ensures they are registered on Base.metadata so that
# Alembic autogenerate can discover all tables.

from app.db.session import Base
from app.models.audit.audit_log import AuditLog
from app.models.catalog.arcade import Machine, PlaySession, PriceRevision, PricingSchedule
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
    DeviceOutage,
    DeviceTelemetry,
    DeviceToken,
    Firmware,
    FirmwareUpdate,
)
from app.models.identity.customer import CustomerIdentity, CustomerSession, PaymentCheckout
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
from app.models.ledger.operations import FinancialControl, ReconciliationRun, TransactionAllocation
from app.models.ledger.wallet import (
    Customer,
    LedgerAccount,
    LedgerEntry,
    Refund,
    Transaction,
    Wallet,
    WalletTransfer,
)
from app.models.tenant.exports import ExportJob
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
from app.models.tenant.venue import (
    CashierShift,
    CashMovement,
    FamilyRelationship,
    OperationalAlert,
    Receipt,
    SpendingLimit,
    TopupPackage,
)
from app.models.tenant.webhook_delivery import WebhookDelivery

__all__ = [
    "ApiKey",
    "AuditLog",
    "Base",
    "BillingSettings",
    "Card",
    "CashMovement",
    "CashierShift",
    "Customer",
    "CustomerIdentity",
    "CustomerSession",
    "Device",
    "DeviceCommand",
    "DeviceConfig",
    "DeviceEvent",
    "DeviceHeartbeat",
    "DeviceOutage",
    "DeviceTelemetry",
    "DeviceToken",
    "ExportJob",
    "ExternalTopupSession",
    "FamilyRelationship",
    "FinancialControl",
    "Firmware",
    "FirmwareUpdate",
    "Hold",
    "Kiosk",
    "KioskLog",
    "KioskTopupSession",
    "LedgerAccount",
    "LedgerEntry",
    "Location",
    "Machine",
    "Membership",
    "Notification",
    "OfflinePolicy",
    "OfflineTransaction",
    "OperationalAlert",
    "OrgSettings",
    "Organization",
    "PaymentCheckout",
    "PaymentMethod",
    "Permission",
    "PlaySession",
    "PriceRevision",
    "PricingSchedule",
    "Product",
    "ProductCategory",
    "Receipt",
    "ReconciliationRun",
    "RefreshToken",
    "Refund",
    "Role",
    "RolePermission",
    "SecuritySettings",
    "SpendingLimit",
    "TempCardAssignment",
    "TopupPackage",
    "Transaction",
    "TransactionAllocation",
    "User",
    "Wallet",
    "WalletTransfer",
    "Webhook",
    "WebhookDelivery",
]
