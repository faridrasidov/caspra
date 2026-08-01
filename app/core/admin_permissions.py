import enum


class AdminPermission(enum.StrEnum):
    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    CARDS_READ = "cards:read"
    CARDS_WRITE = "cards:write"
    WALLETS_READ = "wallets:read"
    WALLETS_ADJUST = "wallets:adjust"
    TRANSACTIONS_READ = "transactions:read"
    TRANSACTIONS_REFUND = "transactions:refund"
    DEVICES_READ = "devices:read"
    DEVICES_MANAGE = "devices:manage"
    INTEGRATIONS_MANAGE = "integrations:manage"
    REPORTS_READ = "reports:read"
    AUDIT_READ = "audit:read"
    SETTINGS_MANAGE = "settings:manage"
    USERS_MANAGE = "users:manage"


def all_admin_permissions() -> list[str]:
    return [permission.value for permission in AdminPermission]
