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
    ORG_READ = "org:read"
    SETTINGS_READ = "settings:read"
    DEVICES_CREDENTIALS = "devices:credentials"
    MACHINES_READ = "machines:read"
    MACHINES_MANAGE = "machines:manage"
    PLAYS_READ = "plays:read"
    PLAYS_RESOLVE = "plays:resolve"
    SHIFTS_OPERATE = "shifts:operate"
    SHIFTS_REVIEW = "shifts:review"
    CASHIER_TOPUP = "cashier:topup"
    PRICING_MANAGE = "pricing:manage"
    FAMILY_MANAGE = "family:manage"
    PORTAL_MANAGE = "portal:manage"
    FINANCIAL_CONTROLS = "financial:controls"
    ALERTS_READ = "alerts:read"


def all_admin_permissions() -> list[str]:
    return [permission.value for permission in AdminPermission]


STAFF_ROLES = {
    "owner": set(all_admin_permissions()),
    "manager": set(all_admin_permissions())
    - {"users:manage", "devices:credentials", "integrations:manage", "financial:controls"},
    "cashier": {
        "customers:read",
        "customers:write",
        "cards:read",
        "cards:write",
        "wallets:read",
        "transactions:read",
        "org:read",
        "shifts:operate",
        "cashier:topup",
        "portal:manage",
    },
    "technician": {
        "devices:read",
        "devices:manage",
        "machines:read",
        "machines:manage",
        "org:read",
        "alerts:read",
    },
}
