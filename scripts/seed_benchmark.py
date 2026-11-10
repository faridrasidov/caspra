"""Create synthetic benchmark data in a NEW PostgreSQL database ending in _bench.

No deletion or reset is performed. Refuses a database that already has a venue.
Credentials in the generated manifest are exclusively for these synthetic readers.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import encrypt_device_secret, generate_device_secret, hash_password
from app.models.catalog.arcade import Machine, PriceRevision
from app.models.device.device import Card, Device
from app.models.identity.user import User
from app.models.ledger.wallet import Customer, Wallet
from app.models.tenant.organization import Organization
from app.schemas.wallet import WalletTopupRequest
from app.services.ledger import LedgerService
from app.services.operations import OperationsService


class BenchmarkSeeder:
    async def run(self, args, url, password):
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            exists = await connection.scalar(text("SELECT to_regclass('organizations')"))
            if exists and await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM organizations)")
            ):
                raise ValueError("Benchmark database already contains venues; use a fresh database")

            def migrate(sync_connection):
                config = Config("alembic.ini")
                config.attributes["connection"] = sync_connection
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        manifest = {"venue_slug": "sandbox-benchmark", "readers": []}
        async with factory() as db:
            org = Organization(
                name="Synthetic benchmark", slug=manifest["venue_slug"], default_currency="USD"
            )
            db.add(org)
            await db.commit()
            roles = await OperationsService().roles(db)
            db.add(
                User(
                    tenant_id=org.id,
                    email=args.email,
                    hashed_password=hash_password(password),
                    role_id=next(row["id"] for row in roles if row["name"] == "owner"),
                )
            )
            await db.commit()
            for index in range(args.readers):
                customer = Customer(tenant_id=org.id, full_name=f"Synthetic player {index}")
                secret = generate_device_secret()
                device = Device(
                    tenant_id=org.id,
                    name=f"Synthetic reader {index}",
                    type="reader",
                    status="active",
                    hmac_secret_encrypted=encrypt_device_secret(secret),
                )
                db.add_all([customer, device])
                await db.flush()
                wallet = Wallet(
                    tenant_id=org.id, customer_id=customer.id, currency="USD", type="credit"
                )
                card_uid = f"BENCH-{index}"
                machine = Machine(
                    tenant_id=org.id,
                    device_id=device.id,
                    name=f"Synthetic machine {index}",
                    price_minor=100,
                    currency="USD",
                )
                db.add_all(
                    [
                        wallet,
                        machine,
                        Card(
                            tenant_id=org.id,
                            uid=card_uid,
                            customer_id=customer.id,
                            type="rfid",
                            status="active",
                        ),
                    ]
                )
                await db.flush()
                db.add(
                    PriceRevision(
                        tenant_id=org.id,
                        machine_id=machine.id,
                        revision=1,
                        price_minor=100,
                        currency="USD",
                    )
                )
                await db.commit()
                await LedgerService().topup(
                    db,
                    org.id,
                    wallet.id,
                    WalletTopupRequest(
                        amount_minor=10_000_000, currency="USD", idempotency_key=uuid4()
                    ),
                )
                manifest["readers"].append(
                    {"device_id": str(device.id), "secret": secret, "card_uid": card_uid}
                )
            # Bulk synthetic paid credits, with balanced immutable entries and matching caches.
            # The count is rounded down to an equal number of history rows per reader.
            remaining = args.history_rows // args.readers
            while remaining:
                count = min(100, remaining)
                await db.execute(
                    text("""
                    WITH inserted AS (
                        INSERT INTO transactions (id,tenant_id,idempotency_key,type,amount_minor,
                            currency,status,wallet_id,customer_id,description,created_at,updated_at)
                        SELECT gen_random_uuid(),w.tenant_id,gen_random_uuid(),'credit',1,'USD',
                            'posted',w.id,w.customer_id,'Synthetic benchmark history',
                            now()-interval '1 day'*((g.i % 30)+1),now()
                        FROM wallets w CROSS JOIN generate_series(1,:count) AS g(i)
                        WHERE w.tenant_id=:tenant AND w.type='credit'
                        RETURNING id,tenant_id,wallet_id,currency
                    )
                    INSERT INTO ledger_entries (id,tenant_id,transaction_id,account_id,wallet_id,
                        direction,amount_minor,currency,created_at,updated_at)
                    SELECT gen_random_uuid(),t.tenant_id,t.id,a.id,t.wallet_id,
                        'credit',1,t.currency,now(),now()
                    FROM inserted t JOIN ledger_accounts a ON a.wallet_id=t.wallet_id
                    UNION ALL
                    SELECT gen_random_uuid(),t.tenant_id,t.id,a.id,NULL,
                        'debit',1,t.currency,now(),now()
                    FROM inserted t JOIN ledger_accounts a ON a.tenant_id=t.tenant_id
                        AND a.type='cash_clearing' AND a.currency=t.currency
                """),
                    {"count": count, "tenant": org.id},
                )
                await db.execute(
                    text(
                        "UPDATE wallets SET balance_minor=balance_minor+:count "
                        "WHERE tenant_id=:tenant AND type='credit'"
                    ),
                    {"count": count, "tenant": org.id},
                )
                await db.commit()
                remaining -= count
            manifest["synthetic_history_rows"] = (args.history_rows // args.readers) * args.readers
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding="utf8")
            print(
                f"Created {args.readers} synthetic readers and "
                f"{manifest['synthetic_history_rows']} history rows. Manifest: {args.output}"
            )
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readers", type=int, default=100)
    parser.add_argument("--history-rows", type=int, default=1_000_000)
    parser.add_argument("--email", default="owner@benchmark.test")
    parser.add_argument("--output", type=Path, default=Path(".benchmark/manifest.json"))
    args = parser.parse_args()
    url, password = os.environ.get("DATABASE_URL", ""), os.environ.get("CASPRA_BENCH_PASSWORD", "")
    if not url.startswith("postgresql+asyncpg://") or not (make_url(url).database or "").endswith(
        "_bench"
    ):
        parser.error("Set DATABASE_URL to a dedicated PostgreSQL database ending in _bench")
    if len(password) < 12 or args.readers < 1 or args.history_rows < 0:
        parser.error("Set a 12-character CASPRA_BENCH_PASSWORD and valid fixture sizes")
    await BenchmarkSeeder().run(args, url, password)


if __name__ == "__main__":
    asyncio.run(main())
