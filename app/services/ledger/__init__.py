# app/services/ledger/__init__.py

from app.services.ledger.charges import ChargeOperations
from app.services.ledger.holds import HoldOperations
from app.services.ledger.wallets import WalletOperations


class LedgerService(WalletOperations, ChargeOperations, HoldOperations):
    """Core money movement: top-up, deduct, transfer, charge, refund and holds.

    Enforces integer minor units, idempotency, row-level locking, append-only
    double-entry, and tenant isolation. Each group of operations lives in its
    own module; shared plumbing is in ``_base``.
    """


__all__ = ["LedgerService"]
