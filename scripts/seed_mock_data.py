"""Create a demo tenant with coherent mock activity from the last 30 days.

The seeder is additive and atomic. It refuses to overwrite an existing tenant,
and all value movements include balanced double-entry ledger rows.
"""

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
import hashlib
import os
from pathlib import Path
import random
import re
import secrets
import sys
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.core.scopes import all_scopes  # noqa: E402
from app.core.security import (  # noqa: E402
    encrypt_device_secret,
    generate_device_secret,
    hash_password,
)
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.models.audit.audit_log import AuditLog  # noqa: E402
from app.models.device.device import Card, Device, DeviceConfig  # noqa: E402
from app.models.identity.user import ApiKey, Role, User  # noqa: E402
from app.models.ledger.hold import OfflineTransaction  # noqa: E402
from app.models.ledger.wallet import (  # noqa: E402
    Customer,
    LedgerAccount,
    LedgerEntry,
    Refund,
    Transaction,
    Wallet,
)
from app.models.tenant.organization import (  # noqa: E402
    Location,
    Membership,
    OfflinePolicy,
    Organization,
    OrgSettings,
    Webhook,
)
from app.models.tenant.webhook_delivery import WebhookDelivery  # noqa: E402

DEFAULT_DAYS = 30
DEFAULT_CUSTOMERS = 40
DEFAULT_TRANSACTIONS_PER_DAY = 18
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIRST_NAMES = (
    "Alex",
    "Amina",
    "Daniel",
    "Elena",
    "Farah",
    "George",
    "Hana",
    "Ivan",
    "Leyla",
    "Marcus",
    "Nadia",
    "Omar",
)
LAST_NAMES = (
    "Aliyev",
    "Bennett",
    "Chen",
    "Davis",
    "Garcia",
    "Hasanov",
    "Ivanov",
    "Karim",
    "Morgan",
    "Novak",
    "Patel",
    "Rahimi",
)


@dataclass(slots=True, frozen=True)
class SeedConfig:
    tenant_slug: str
    tenant_name: str
    admin_email: str
    admin_password: str
    days: int = DEFAULT_DAYS
    customers: int = DEFAULT_CUSTOMERS
    transactions_per_day: int = DEFAULT_TRANSACTIONS_PER_DAY
    currency: str = "USD"
    random_seed: int = 20260810


@dataclass(slots=True)
class Dataset:
    organization: Organization
    admin: User
    customers: list[Customer]
    wallets: list[Wallet]
    cards: list[Card]
    devices: list[Device]
    webhook: Webhook
    api_key: str
    first_device_secret: str


@dataclass(slots=True, frozen=True)
class SeedResult:
    tenant_id: UUID
    tenant_slug: str
    admin_email: str
    admin_password: str
    api_key: str
    first_device_id: UUID
    first_device_secret: str
    customers: int
    wallets: int
    cards: int
    devices: int
    transactions: int
    refunds: int
    date_from: datetime
    date_to: datetime


def _timestamps(at: datetime) -> dict[str, datetime]:
    return {"created_at": at, "updated_at": at}


def _timestamp_for_day(
    rng: random.Random,
    start: datetime,
    now: datetime,
    day_index: int,
) -> datetime:
    day_start = start + timedelta(days=day_index)
    day_end = min(day_start + timedelta(days=1, microseconds=-1), now)
    available_seconds = max(0, int((day_end - day_start).total_seconds()))
    return day_start + timedelta(seconds=rng.randint(0, available_seconds))


def _validate_config(config: SeedConfig) -> None:
    if not SLUG_PATTERN.fullmatch(config.tenant_slug):
        raise ValueError("Tenant slug must contain lowercase letters, numbers, and hyphens only")
    if not 1 <= config.days <= 365:
        raise ValueError("Days must be between 1 and 365")
    if not 5 <= config.customers <= 5000:
        raise ValueError("Customers must be between 5 and 5000")
    if not 1 <= config.transactions_per_day <= 10000:
        raise ValueError("Transactions per day must be between 1 and 10000")
    if len(config.currency) != 3 or not config.currency.isalpha():
        raise ValueError("Currency must be a three-letter code")


async def _ensure_new_tenant(db: AsyncSession, slug: str) -> None:
    existing = (
        await db.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if existing is not None:
        raise RuntimeError(
            f"Tenant slug '{slug}' already exists. Choose another --tenant-slug; "
            "the seeder never overwrites data."
        )


async def _seed_entities(
    db: AsyncSession,
    config: SeedConfig,
    start: datetime,
    now: datetime,
) -> Dataset:
    organization = Organization(
        id=uuid4(),
        name=config.tenant_name,
        slug=config.tenant_slug,
        status="active",
        default_currency=config.currency,
        **_timestamps(start),
    )
    db.add(organization)

    role = (await db.execute(select(Role).where(Role.name == "admin"))).scalars().first()
    if role is None:
        role = Role(
            id=uuid4(),
            name="admin",
            description="Built-in tenant administrator",
            is_system=True,
            **_timestamps(start),
        )
        db.add(role)
    # These models intentionally expose FK columns without ORM relationships.
    # Flush each dependency layer explicitly so PostgreSQL never sees a child
    # row before its referenced parent. The surrounding transaction remains
    # atomic; none of these flushes commit data.
    await db.flush()

    admin = User(
        id=uuid4(),
        tenant_id=organization.id,
        email=config.admin_email,
        hashed_password=hash_password(config.admin_password),
        full_name="Caspra Demo Admin",
        status="active",
        role_id=role.id,
        **_timestamps(start),
    )
    db.add(admin)
    await db.flush()
    db.add_all(
        [
            Membership(
                id=uuid4(),
                tenant_id=organization.id,
                user_id=admin.id,
                role_id=role.id,
                status="active",
                **_timestamps(start),
            ),
            OrgSettings(
                id=uuid4(),
                tenant_id=organization.id,
                timezone="UTC",
                branding={"display_name": config.tenant_name, "accent": "#2563eb"},
                config={"demo_data": True, "data_window_days": config.days},
                **_timestamps(start),
            ),
            OfflinePolicy(
                id=uuid4(),
                tenant_id=organization.id,
                enabled=True,
                uid_risk_accepted=True,
                max_transaction_minor=2500,
                max_card_total_minor=7500,
                max_device_total_minor=50000,
                max_outage_total_minor=150000,
                max_queue_age_seconds=86400,
                max_queue_size=200,
                sync_interval_seconds=60,
                **_timestamps(start),
            ),
        ]
    )

    locations = [
        Location(
            id=uuid4(),
            tenant_id=organization.id,
            name=name,
            address=address,
            timezone="UTC",
            status="active",
            **_timestamps(start + timedelta(hours=index)),
        )
        for index, (name, address) in enumerate(
            (
                ("Atrium Cafe", "12 Market Street"),
                ("Arcade Hall", "8 Harbor Avenue"),
                ("Event Pavilion", "31 Riverside Walk"),
            )
        )
    ]
    db.add_all(locations)
    await db.flush()

    customers: list[Customer] = []
    wallets: list[Wallet] = []
    cards: list[Card] = []
    for index in range(config.customers):
        first = FIRST_NAMES[index % len(FIRST_NAMES)]
        last = LAST_NAMES[(index * 3) % len(LAST_NAMES)]
        customer = Customer(
            id=uuid4(),
            tenant_id=organization.id,
            external_id=f"DEMO-CUST-{index + 1:04d}",
            full_name=f"{first} {last}",
            email=f"customer{index + 1:04d}.{config.tenant_slug}@example.test",
            phone=f"+1555{index + 1:07d}",
            status="blocked" if index == config.customers - 1 else "active",
            **_timestamps(start + timedelta(minutes=index)),
        )
        wallet = Wallet(
            id=uuid4(),
            tenant_id=organization.id,
            customer_id=customer.id,
            balance_minor=0,
            currency=config.currency,
            type="credit",
            status="frozen" if index == config.customers - 1 else "active",
            **_timestamps(start + timedelta(minutes=index)),
        )
        card = Card(
            id=uuid4(),
            tenant_id=organization.id,
            uid=f"DEMO-{config.tenant_slug.upper()}-{index + 1:06d}",
            type=("rfid", "nfc", "wristband")[index % 3],
            status="blocked" if index == config.customers - 1 else "active",
            customer_id=customer.id,
            **_timestamps(start + timedelta(minutes=index)),
        )
        customers.append(customer)
        wallets.append(wallet)
        cards.append(card)
    db.add_all(customers)
    await db.flush()
    db.add_all([*wallets, *cards])
    await db.flush()

    devices: list[Device] = []
    device_configs: list[DeviceConfig] = []
    first_device_secret = ""
    for index in range(8):
        device_secret = generate_device_secret()
        if index == 0:
            first_device_secret = device_secret
        device = Device(
            id=uuid4(),
            tenant_id=organization.id,
            name=f"{locations[index % len(locations)].name} Terminal {index + 1}",
            serial=f"DEMO-TERM-{index + 1:04d}",
            type="pos" if index % 3 == 0 else "reader",
            status="inactive" if index == 7 else "active",
            location_id=locations[index % len(locations)].id,
            hmac_secret_encrypted=encrypt_device_secret(device_secret),
            hmac_secret_version=1,
            **_timestamps(start + timedelta(hours=index)),
        )
        devices.append(device)
        device_configs.append(
            DeviceConfig(
                id=uuid4(),
                tenant_id=organization.id,
                device_id=device.id,
                config={"mode": "demo", "receipt": index % 2 == 0},
                **_timestamps(start + timedelta(hours=index)),
            )
        )
    db.add_all(devices)
    await db.flush()
    db.add_all(device_configs)
    await db.flush()

    api_key = f"caspra_demo_{secrets.token_urlsafe(24)}"
    webhook = Webhook(
        id=uuid4(),
        tenant_id=organization.id,
        url="https://example.test/caspra-webhook",
        events=["transaction.posted", "transaction.refunded"],
        secret=secrets.token_urlsafe(32),
        active=True,
        **_timestamps(start),
    )
    db.add(webhook)
    await db.flush()
    db.add(
        ApiKey(
            id=uuid4(),
            tenant_id=organization.id,
            name="Demo integration key",
            prefix=api_key[:16],
            key_hash=hashlib.sha256(api_key.encode()).hexdigest(),
            scopes=all_scopes(),
            revoked=False,
            user_id=admin.id,
            **_timestamps(now),
        )
    )
    await db.flush()
    return Dataset(
        organization=organization,
        admin=admin,
        customers=customers,
        wallets=wallets,
        cards=cards,
        devices=devices,
        webhook=webhook,
        api_key=api_key,
        first_device_secret=first_device_secret,
    )


def _create_ledger_accounts(
    db: AsyncSession,
    dataset: Dataset,
    currency: str,
    start: datetime,
) -> tuple[dict[UUID, LedgerAccount], LedgerAccount, LedgerAccount]:
    tenant_id = dataset.organization.id
    wallet_accounts = {
        wallet.id: LedgerAccount(
            id=uuid4(),
            tenant_id=tenant_id,
            code=f"wallet:{wallet.id}",
            type="wallet_liability",
            currency=currency,
            status="active",
            wallet_id=wallet.id,
            **_timestamps(start),
        )
        for wallet in dataset.wallets
    }
    cash_account = LedgerAccount(
        id=uuid4(),
        tenant_id=tenant_id,
        code=f"cash_clearing:{currency}",
        type="cash_clearing",
        currency=currency,
        status="active",
        **_timestamps(start),
    )
    revenue_account = LedgerAccount(
        id=uuid4(),
        tenant_id=tenant_id,
        code=f"merchant_revenue:{currency}",
        type="merchant_revenue",
        currency=currency,
        status="active",
        **_timestamps(start),
    )
    db.add_all([*wallet_accounts.values(), cash_account, revenue_account])
    return wallet_accounts, cash_account, revenue_account


def _add_transaction(
    db: AsyncSession,
    *,
    dataset: Dataset,
    wallet: Wallet,
    wallet_account: LedgerAccount,
    system_account: LedgerAccount,
    transaction_type: str,
    amount_minor: int,
    currency: str,
    at: datetime,
    description: str,
    device_id: UUID | None = None,
) -> tuple[Transaction, tuple[LedgerEntry, LedgerEntry]]:
    transaction = Transaction(
        id=uuid4(),
        tenant_id=dataset.organization.id,
        idempotency_key=uuid4(),
        request_hash=hashlib.sha256(f"mock:{uuid4()}".encode()).hexdigest(),
        type=transaction_type,
        amount_minor=amount_minor,
        currency=currency,
        status="posted",
        wallet_id=wallet.id,
        customer_id=wallet.customer_id,
        device_id=device_id,
        description=description,
        **_timestamps(at),
    )
    incoming = transaction_type in {"credit", "refund"}
    wallet.balance_minor += amount_minor if incoming else -amount_minor
    wallet.updated_at = at
    entries = (
        LedgerEntry(
            id=uuid4(),
            tenant_id=dataset.organization.id,
            transaction_id=transaction.id,
            account_id=wallet_account.id,
            wallet_id=wallet.id,
            direction="credit" if incoming else "debit",
            amount_minor=amount_minor,
            currency=currency,
            **_timestamps(at),
        ),
        LedgerEntry(
            id=uuid4(),
            tenant_id=dataset.organization.id,
            transaction_id=transaction.id,
            account_id=system_account.id,
            wallet_id=None,
            direction="debit" if incoming else "credit",
            amount_minor=amount_minor,
            currency=currency,
            **_timestamps(at),
        ),
    )
    db.add(transaction)
    return transaction, entries


async def _seed_transactions(
    db: AsyncSession,
    dataset: Dataset,
    config: SeedConfig,
    start: datetime,
    now: datetime,
    rng: random.Random,
) -> tuple[list[Transaction], list[Refund]]:
    wallet_accounts, cash_account, revenue_account = _create_ledger_accounts(
        db, dataset, config.currency, start
    )
    await db.flush()
    transactions: list[Transaction] = []
    entries: list[LedgerEntry] = []
    refunds: list[Refund] = []

    for index, wallet in enumerate(dataset.wallets):
        transaction, transaction_entries = _add_transaction(
            db,
            dataset=dataset,
            wallet=wallet,
            wallet_account=wallet_accounts[wallet.id],
            system_account=cash_account,
            transaction_type="credit",
            amount_minor=rng.randint(400, 900) * 100,
            currency=config.currency,
            at=start + timedelta(minutes=index + 1),
            description="Opening demo balance",
        )
        transactions.append(transaction)
        entries.extend(transaction_entries)

    active_wallets = dataset.wallets[:-1]
    active_devices = dataset.devices[:-1]
    sale_amounts = (250, 350, 425, 500, 650, 725, 850, 975, 1200, 1500, 2500)
    for day_index in range(config.days):
        for _ in range(config.transactions_per_day):
            at = _timestamp_for_day(rng, start, now, day_index)
            wallet = rng.choice(active_wallets)
            if rng.random() < 0.22:
                transaction, transaction_entries = _add_transaction(
                    db,
                    dataset=dataset,
                    wallet=wallet,
                    wallet_account=wallet_accounts[wallet.id],
                    system_account=cash_account,
                    transaction_type="credit",
                    amount_minor=rng.randint(10, 75) * 100,
                    currency=config.currency,
                    at=at,
                    description=rng.choice(("Kiosk reload", "Mobile top-up", "Counter top-up")),
                )
            else:
                amount_minor = rng.choice(sale_amounts)
                amount_minor = min(amount_minor, wallet.balance_minor)
                if amount_minor <= 0:
                    continue
                transaction, transaction_entries = _add_transaction(
                    db,
                    dataset=dataset,
                    wallet=wallet,
                    wallet_account=wallet_accounts[wallet.id],
                    system_account=revenue_account,
                    transaction_type="debit",
                    amount_minor=amount_minor,
                    currency=config.currency,
                    at=at,
                    description=rng.choice(
                        ("Cafe purchase", "Arcade session", "Event pass", "Locker rental")
                    ),
                    device_id=rng.choice(active_devices).id,
                )
                if rng.random() < 0.06:
                    refund_at = min(at + timedelta(minutes=rng.randint(5, 240)), now)
                    refund_amount = (
                        amount_minor if rng.random() < 0.65 else max(1, amount_minor // 2)
                    )
                    refund_transaction, refund_entries = _add_transaction(
                        db,
                        dataset=dataset,
                        wallet=wallet,
                        wallet_account=wallet_accounts[wallet.id],
                        system_account=revenue_account,
                        transaction_type="refund",
                        amount_minor=refund_amount,
                        currency=config.currency,
                        at=refund_at,
                        description="Customer service refund",
                    )
                    refund = Refund(
                        id=uuid4(),
                        tenant_id=dataset.organization.id,
                        original_transaction_id=transaction.id,
                        refund_transaction_id=refund_transaction.id,
                        amount_minor=refund_amount,
                        currency=config.currency,
                        reason="Demo customer service refund",
                        status="completed",
                        **_timestamps(refund_at),
                    )
                    if refund_amount == amount_minor:
                        transaction.status = "reversed"
                        transaction.updated_at = refund_at
                    refunds.append(refund)
                    transactions.append(refund_transaction)
                    entries.extend(refund_entries)
            transactions.append(transaction)
            entries.extend(transaction_entries)
    # Transactions must exist before immutable entries and refund rows point
    # at them. Keep the inserts batched while making that order explicit.
    await db.flush()
    db.add_all(entries)
    await db.flush()
    db.add_all(refunds)
    await db.flush()
    return transactions, refunds


def _seed_operational_rows(
    db: AsyncSession,
    dataset: Dataset,
    transactions: list[Transaction],
    config: SeedConfig,
    start: datetime,
    now: datetime,
) -> None:
    tenant_id = dataset.organization.id
    for index in range(5):
        device = dataset.devices[index]
        card = dataset.cards[index]
        occurred_at = now - timedelta(minutes=30 + index * 25)
        idempotency_key = uuid4()
        payload = {
            "idempotency_key": str(idempotency_key),
            "type": "debit",
            "card_uid": card.uid,
            "amount_minor": 300 + index * 125,
            "currency": config.currency,
            "occurred_at": occurred_at.isoformat(),
            "sequence_number": 9000 + index,
            "description": "Demo offline purchase",
        }
        db.add(
            OfflineTransaction(
                id=uuid4(),
                tenant_id=tenant_id,
                device_id=device.id,
                idempotency_key=idempotency_key,
                request_hash=hashlib.sha256(str(payload).encode()).hexdigest(),
                occurred_at=occurred_at,
                sequence_number=9000 + index,
                card_uid=card.uid,
                amount_minor=300 + index * 125,
                payload=payload,
                status="manual_review",
                error="Sequence gap detected in demo offline queue",
                **_timestamps(occurred_at),
            )
        )

    statuses = ("dead", "retrying", "failed", "success", "pending", "success")
    for index in range(18):
        status = statuses[index % len(statuses)]
        at = now - timedelta(hours=index * 7)
        transaction = transactions[-(index % len(transactions)) - 1]
        db.add(
            WebhookDelivery(
                id=uuid4(),
                tenant_id=tenant_id,
                webhook_id=dataset.webhook.id,
                event_type="transaction.refunded"
                if transaction.type == "refund"
                else "transaction.posted",
                payload={"transaction_id": str(transaction.id), "demo": True},
                status=status,
                attempts=5 if status == "dead" else (2 if status in {"retrying", "failed"} else 1),
                response_code=200
                if status == "success"
                else (503 if status != "pending" else None),
                response_body="accepted" if status == "success" else None,
                error="Demo endpoint returned 503"
                if status in {"dead", "retrying", "failed"}
                else None,
                next_retry_at=at + timedelta(hours=1) if status == "retrying" else None,
                delivered_at=at + timedelta(seconds=2) if status == "success" else None,
                **_timestamps(at),
            )
        )

    actions = (
        "customer.created",
        "card.assigned",
        "wallet.topped_up",
        "device.registered",
        "settings.updated",
    )
    for index in range(25):
        at = start + timedelta(days=index % config.days, hours=index % 12)
        db.add(
            AuditLog(
                id=uuid4(),
                tenant_id=tenant_id,
                actor_user_id=dataset.admin.id,
                action=actions[index % len(actions)],
                target_type="demo_resource",
                target_id=str(dataset.customers[index % len(dataset.customers)].id),
                payload={"seeded": True, "sequence": index + 1},
                **_timestamps(at),
            )
        )


async def seed_mock_data(db: AsyncSession, config: SeedConfig) -> SeedResult:
    """Add one complete demo tenant to an already-migrated database."""
    _validate_config(config)
    await _ensure_new_tenant(db, config.tenant_slug)
    rng = random.Random(config.random_seed)  # noqa: S311 - deterministic demo data
    now = datetime.now(UTC)
    start = datetime.combine(now.date() - timedelta(days=config.days - 1), time.min, tzinfo=UTC)
    dataset = await _seed_entities(db, config, start, now)
    transactions, refunds = await _seed_transactions(db, dataset, config, start, now, rng)
    _seed_operational_rows(db, dataset, transactions, config, start, now)
    await db.flush()
    return SeedResult(
        tenant_id=dataset.organization.id,
        tenant_slug=dataset.organization.slug,
        admin_email=dataset.admin.email,
        admin_password=config.admin_password,
        api_key=dataset.api_key,
        first_device_id=dataset.devices[0].id,
        first_device_secret=dataset.first_device_secret,
        customers=len(dataset.customers),
        wallets=len(dataset.wallets),
        cards=len(dataset.cards),
        devices=len(dataset.devices),
        transactions=len(transactions),
        refunds=len(refunds),
        date_from=start,
        date_to=now,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a separate Caspra demo tenant with 30 days of mock data."
    )
    parser.add_argument("--tenant-slug", default="demo-30d")
    parser.add_argument("--tenant-name", default="Caspra 30-Day Demo")
    parser.add_argument("--admin-email")
    parser.add_argument(
        "--admin-password",
        default=os.getenv("CASPRA_DEMO_ADMIN_PASSWORD"),
        help="Demo admin password; generated when omitted.",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--customers", type=int, default=DEFAULT_CUSTOMERS)
    parser.add_argument("--transactions-per-day", type=int, default=DEFAULT_TRANSACTIONS_PER_DAY)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--random-seed", type=int, default=20260810)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate every row, then roll the transaction back.",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Required when ENVIRONMENT=production.",
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> SeedConfig:
    return SeedConfig(
        tenant_slug=args.tenant_slug,
        tenant_name=args.tenant_name,
        admin_email=(args.admin_email or f"admin+{args.tenant_slug}@caspra.local").lower(),
        admin_password=args.admin_password or secrets.token_urlsafe(15),
        days=args.days,
        customers=args.customers,
        transactions_per_day=args.transactions_per_day,
        currency=args.currency.upper(),
        random_seed=args.random_seed,
    )


def _print_result(result: SeedResult, *, dry_run: bool) -> None:
    print(f"\nMock data seed: {'DRY RUN (rolled back)' if dry_run else 'COMMITTED'}")
    print(f"Tenant:          {result.tenant_slug} ({result.tenant_id})")
    print(f"Date range:      {result.date_from.isoformat()} -> {result.date_to.isoformat()}")
    print(f"Admin email:     {result.admin_email}")
    print(f"Admin password:  {result.admin_password}")
    print(f"Public API key:  {result.api_key}")
    print(f"First device:    {result.first_device_id}")
    print(f"Device secret:   {result.first_device_secret}")
    print(
        "Rows:            "
        f"{result.customers} customers, {result.wallets} wallets, {result.cards} cards, "
        f"{result.devices} devices, {result.transactions} transactions, "
        f"{result.refunds} refunds"
    )
    if dry_run:
        print("No rows were persisted. Run again without --dry-run to insert them.")


async def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if settings.environment == "production" and not args.allow_production:
        parser.error("Refusing production database access without --allow-production")
    config = _config_from_args(args)
    _validate_config(config)
    safe_url = make_url(settings.database_url).render_as_string(hide_password=True)
    print(f"Database: {safe_url}")
    engine = create_engine(settings.database_url, echo=False)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as db:
            try:
                result = await seed_mock_data(db, config)
                if args.dry_run:
                    await db.rollback()
                else:
                    await db.commit()
            except BaseException:
                await db.rollback()
                raise
    finally:
        await engine.dispose()
    _print_result(result, dry_run=args.dry_run)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args, parser))
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
