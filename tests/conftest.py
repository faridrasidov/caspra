# tests/conftest.py

from collections.abc import AsyncGenerator
import hashlib
import hmac
import json
import os
import secrets
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEVICE_HMAC_SECRET", "test-device-secret")

from app.core.config import get_settings

get_settings.cache_clear()

from app.core.config import settings  # noqa: E402
from app.core.scopes import all_scopes  # noqa: E402
from app.core.security import (  # noqa: E402
    build_device_signature_v2,
    create_access_token,
    encrypt_device_secret,
    generate_device_secret,
    hash_password,
)
from app.db.session import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.catalog.product import Product, ProductCategory  # noqa: E402
from app.models.device.device import Card, Device  # noqa: E402
from app.models.identity.user import ApiKey, Role, User  # noqa: E402
from app.models.ledger.wallet import Customer, Wallet  # noqa: E402
from app.models.tenant.organization import (  # noqa: E402
    Membership,
    MembershipStatus,
    OfflinePolicy,
    Organization,
)

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


async def _seed_tenant_admin(
    session_factory,
    *,
    slug: str,
    admin_email: str,
    role_name: str,
) -> dict[str, str]:
    """Create an organization, admin role, an admin user, and a membership.

    ``role_name`` must be one of ``deps.ADMIN_ROLE_NAMES`` for the user to pass
    the admin gate. Role names are globally unique, so each tenant uses a
    distinct admin-level role name (e.g. ``admin`` and ``owner``).
    """
    async with session_factory() as session:
        org = Organization(name=f"Org {slug}", slug=slug, default_currency="USD")
        session.add(org)
        await session.flush()

        role = Role(name=role_name, description="Tenant admin", is_system=True)
        session.add(role)
        await session.flush()

        admin = User(
            tenant_id=org.id,
            email=admin_email,
            hashed_password=hash_password("adminpassword"),
            full_name="Admin User",
            role_id=role.id,
        )
        session.add(admin)
        await session.flush()

        session.add(
            Membership(
                tenant_id=org.id,
                user_id=admin.id,
                role_id=role.id,
                status=MembershipStatus.ACTIVE.value,
            )
        )
        await session.commit()
        return {"user_id": str(admin.id), "tenant_id": str(org.id), "role_id": str(role.id)}


@pytest.fixture
async def db_engine():
    engine_kwargs = {"echo": False}
    if TEST_DATABASE_URL.startswith("sqlite"):
        # Keep one connection so an in-memory SQLite database is shared by the app.
        engine_kwargs.update(
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    engine = create_async_engine(TEST_DATABASE_URL, **engine_kwargs)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_engine) -> AsyncGenerator[AsyncClient]:
    app = create_app()
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    app.state.engine = db_engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user_id() -> str:
    return str(uuid4())


@pytest.fixture
async def seeded_admin(db_engine) -> dict[str, str]:
    """Seed the primary tenant with an admin user."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_tenant_admin(
        session_factory, slug="primary", admin_email="admin@primary.test", role_name="admin"
    )


@pytest.fixture
async def seeded_admin_other(db_engine) -> dict[str, str]:
    """Seed a second tenant with its own admin user (for isolation tests)."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_tenant_admin(
        session_factory, slug="secondary", admin_email="admin@secondary.test", role_name="owner"
    )


@pytest.fixture
async def auth_headers_admin(seeded_admin: dict[str, str]) -> dict[str, str]:
    """Bearer headers for a seeded admin user (primary tenant)."""
    token = create_access_token(seeded_admin["user_id"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_headers_admin_other(seeded_admin_other: dict[str, str]) -> dict[str, str]:
    """Bearer headers for the second tenant's admin user."""
    token = create_access_token(seeded_admin_other["user_id"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user(test_user_id: str) -> dict[str, str]:
    """Bearer headers for a token whose subject is not an admin user (-> 403)."""
    token = create_access_token(test_user_id)
    return {"Authorization": f"Bearer {token}"}


async def _seed_device_env(
    session_factory,
    *,
    slug: str,
    card_uid: str,
    balance_minor: int = 10_000,
    currency: str = "USD",
    device_status: str = "active",
) -> dict[str, str]:
    """Seed an org with a customer, a funded credit wallet, a card, and a device."""
    async with session_factory() as session:
        org = Organization(name=f"Org {slug}", slug=slug, default_currency=currency)
        session.add(org)
        await session.flush()
        session.add(
            OfflinePolicy(
                tenant_id=org.id,
                enabled=True,
                uid_risk_accepted=True,
                max_transaction_minor=2_000,
                max_card_total_minor=5_000,
                max_device_total_minor=10_000,
                max_outage_total_minor=20_000,
                max_queue_age_seconds=3600,
                max_queue_size=100,
                sync_interval_seconds=60,
            )
        )

        customer = Customer(tenant_id=org.id, full_name="Card Holder")
        session.add(customer)
        await session.flush()

        wallet = Wallet(
            tenant_id=org.id,
            customer_id=customer.id,
            balance_minor=balance_minor,
            currency=currency,
            type="credit",
            status="active",
        )
        session.add(wallet)
        await session.flush()

        card = Card(
            tenant_id=org.id,
            uid=card_uid,
            type="rfid",
            status="active",
            customer_id=customer.id,
        )
        session.add(card)
        await session.flush()

        device_secret = generate_device_secret()
        device = Device(
            tenant_id=org.id,
            name="Reader 1",
            type="reader",
            status=device_status,
            hmac_secret_encrypted=encrypt_device_secret(device_secret),
            hmac_secret_version=1,
        )
        session.add(device)
        await session.flush()

        await session.commit()
        return {
            "device_id": str(device.id),
            "tenant_id": str(org.id),
            "customer_id": str(customer.id),
            "wallet_id": str(wallet.id),
            "card_uid": card_uid,
            "currency": currency,
            "balance_minor": str(balance_minor),
            "device_secret": device_secret,
        }


def _sign_device(device_id: str, timestamp: str, body: bytes) -> str:
    message = f"{device_id}:{timestamp}:".encode() + body
    return hmac.new(settings.device_hmac_secret.encode(), message, hashlib.sha256).hexdigest()


@pytest.fixture
async def seeded_device(db_engine) -> dict[str, str]:
    """Seed an active device + card + funded wallet in the primary device tenant."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_device_env(session_factory, slug="device-primary", card_uid="CARD-DEV-1")


@pytest.fixture
async def seeded_device_other(db_engine) -> dict[str, str]:
    """Seed a second device tenant (for cross-tenant isolation tests)."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_device_env(session_factory, slug="device-secondary", card_uid="CARD-DEV-2")


@pytest.fixture
def device_signer():
    """Return a builder for valid HMAC device headers (+ exact signed body bytes).

    Usage:
        headers, body = device_signer(device_id, {"card_uid": "X"})
        await client.post(url, headers=headers, content=body)
    """

    def _make(device_id: str, payload: dict | None = None) -> tuple[dict[str, str], bytes]:
        body = b"" if payload is None else json.dumps(payload).encode()
        headers = {
            "X-Device-Id": device_id,
            "X-Device-Timestamp": "0",
            "X-Device-Signature": _sign_device(device_id, "0", body),
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return headers, body

    return _make


@pytest.fixture
def device_headers(seeded_device: dict[str, str]) -> dict[str, str]:
    """Valid empty-body HMAC headers for the seeded primary device (GET requests)."""
    device_id = seeded_device["device_id"]
    return {
        "X-Device-Id": device_id,
        "X-Device-Timestamp": "0",
        "X-Device-Signature": _sign_device(device_id, "0", b""),
    }


@pytest.fixture
def device_v2_signer():
    """Build HMAC v2 headers for an exact method, path, nonce, and body."""

    def _make(
        device_id: str,
        secret: str,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        nonce: str | None = None,
    ) -> tuple[dict[str, str], bytes]:
        body = b"" if payload is None else json.dumps(payload).encode()
        timestamp = str(int(__import__("time").time()))
        request_nonce = nonce or secrets.token_urlsafe(24)
        signature = build_device_signature_v2(
            secret=secret,
            method=method,
            path=path,
            device_id=device_id,
            timestamp=timestamp,
            nonce=request_nonce,
            body=body,
        )
        headers = {
            "X-Device-Id": device_id,
            "X-Device-Timestamp": timestamp,
            "X-Device-Nonce": request_nonce,
            "X-Device-Signature-Version": "2",
            "X-Device-Signature": signature,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return headers, body

    return _make


# ========== Public Developer API fixtures ==========


def _make_api_key(tenant_id, name: str, scopes: list[str]) -> tuple[ApiKey, str]:
    """Build an ApiKey row with a known raw key (SHA-256 hashed, like the service)."""
    prefix = "csk_" + secrets.token_hex(4)
    raw = f"{prefix}.{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    api_key = ApiKey(
        tenant_id=tenant_id,
        name=name,
        prefix=prefix,
        key_hash=key_hash,
        scopes=scopes,
    )
    return api_key, raw


# Read-only scope bundle: notably excludes customers:write so customer PII is
# redacted for these keys.
_READONLY_SCOPES = [
    "customers:read",
    "cards:read",
    "devices:read",
    "products:read",
    "transactions:read",
    "reports:read",
    "org:read",
]


async def _seed_public_env(
    session_factory,
    *,
    slug: str,
    card_uid: str,
    customer_email: str = "holder@example.test",
    balance_minor: int = 50_000,
    currency: str = "USD",
) -> dict[str, str]:
    """Seed a tenant with a customer, wallet, card, device, product, and API keys."""
    async with session_factory() as session:
        org = Organization(name=f"Org {slug}", slug=slug, default_currency=currency)
        session.add(org)
        await session.flush()

        customer = Customer(
            tenant_id=org.id,
            full_name="Card Holder",
            email=customer_email,
            phone="+15550001111",
        )
        session.add(customer)
        await session.flush()

        wallet = Wallet(
            tenant_id=org.id,
            customer_id=customer.id,
            balance_minor=balance_minor,
            currency=currency,
            type="credit",
            status="active",
        )
        session.add(wallet)
        await session.flush()

        card = Card(
            tenant_id=org.id, uid=card_uid, type="rfid", status="active", customer_id=customer.id
        )
        session.add(card)

        device = Device(tenant_id=org.id, name="Public Reader", type="reader", status="active")
        session.add(device)

        category = ProductCategory(tenant_id=org.id, name="Drinks", slug="drinks")
        session.add(category)
        await session.flush()

        product = Product(
            tenant_id=org.id,
            name="Cola",
            sku=f"SKU-{slug}",
            price_minor=300,
            currency=currency,
            category_id=category.id,
        )
        session.add(product)

        full_key, full_raw = _make_api_key(org.id, "full", all_scopes())
        ro_key, ro_raw = _make_api_key(org.id, "readonly", _READONLY_SCOPES)
        no_key, no_raw = _make_api_key(org.id, "noscope", [])
        session.add_all([full_key, ro_key, no_key])

        await session.flush()
        await session.commit()
        return {
            "tenant_id": str(org.id),
            "customer_id": str(customer.id),
            "wallet_id": str(wallet.id),
            "card_id": str(card.id),
            "card_uid": card_uid,
            "device_id": str(device.id),
            "product_id": str(product.id),
            "category_id": str(category.id),
            "currency": currency,
            "customer_email": customer_email,
            "full_key": full_raw,
            "readonly_key": ro_raw,
            "noscope_key": no_raw,
        }


@pytest.fixture
async def seeded_public(db_engine) -> dict[str, str]:
    """Seed the primary public-API tenant with resources and three API keys."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_public_env(session_factory, slug="public-primary", card_uid="CARD-PUB-1")


@pytest.fixture
async def seeded_public_other(db_engine) -> dict[str, str]:
    """Seed a second public-API tenant (for cross-tenant isolation tests)."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    return await _seed_public_env(
        session_factory,
        slug="public-secondary",
        card_uid="CARD-PUB-2",
        customer_email="other@example.test",
    )


@pytest.fixture
def api_key_headers(seeded_public: dict[str, str]) -> dict[str, str]:
    """Bearer headers for an API key with the full scope set (PII visible)."""
    return {"Authorization": f"Bearer {seeded_public['full_key']}"}


@pytest.fixture
def api_key_headers_readonly(seeded_public: dict[str, str]) -> dict[str, str]:
    """Headers for a read-only key (no customers:write -> PII redacted)."""
    return {"X-API-Key": seeded_public["readonly_key"]}


@pytest.fixture
def api_key_headers_noscope(seeded_public: dict[str, str]) -> dict[str, str]:
    """Headers for a valid key with no scopes (every scoped route -> 403)."""
    return {"Authorization": f"Bearer {seeded_public['noscope_key']}"}


@pytest.fixture
def api_key_headers_other(seeded_public_other: dict[str, str]) -> dict[str, str]:
    """Bearer headers for the second tenant's full-scope API key."""
    return {"Authorization": f"Bearer {seeded_public_other['full_key']}"}
