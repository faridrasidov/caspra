# app/core/scopes.py

import enum


class PublicScope(enum.StrEnum):
    """Canonical scope set for the public developer API.

    A scope is a coarse capability granted to an :class:`ApiKey`. Every public
    route (except open metadata) is gated by exactly one of these scopes.
    """

    CUSTOMERS_READ = "customers:read"
    CUSTOMERS_WRITE = "customers:write"
    CARDS_READ = "cards:read"
    CARDS_WRITE = "cards:write"
    DEVICES_READ = "devices:read"
    PRODUCTS_READ = "products:read"
    TRANSACTIONS_READ = "transactions:read"
    TRANSACTIONS_WRITE = "transactions:write"
    TOPUP_WRITE = "topup:write"
    WEBHOOKS_MANAGE = "webhooks:manage"
    REPORTS_READ = "reports:read"
    ORG_READ = "org:read"


# Customer PII (email/phone) is only exposed to keys holding this elevated
# scope; ``customers:read`` alone yields redacted contact fields. ``write``
# access implies full trust, so it doubles as the PII-visibility scope.
PII_SCOPE = PublicScope.CUSTOMERS_WRITE


def all_scopes() -> list[str]:
    """Return every defined scope as raw strings."""
    return [scope.value for scope in PublicScope]
