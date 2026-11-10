import csv
from datetime import UTC, datetime
import io
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.domain_errors import InsufficientFundsError
from app.core.security import create_access_token, encrypt_device_secret, hash_password
from app.models.device.device import Card, Device
from app.models.identity.user import Role, User
from app.models.ledger.operations import TransactionAllocation
from app.models.ledger.wallet import Customer, Wallet
from app.models.tenant.venue import Receipt
from app.schemas.wallet import WalletTopupRequest, WalletTransferRequest
from app.services.exports import ExportService
from app.services.ledger import LedgerService
from app.services.operations import OperationsService
from scripts.reader_simulator import ReaderJournal, ReaderSimulator

pytestmark = pytest.mark.asyncio
ADMIN = "/admin/api/v1"
DEVICE = "/device/api/v1"
CUSTOMER = "/customer/api/v1"


@pytest.fixture
async def arcade_env(db_session, seeded_admin):
    tenant_id = UUID(seeded_admin["tenant_id"])
    customer = Customer(tenant_id=tenant_id, full_name="Arcade Player")
    db_session.add(customer)
    await db_session.flush()
    paid = Wallet(tenant_id=tenant_id, customer_id=customer.id, currency="USD", type="credit")
    bonus = Wallet(tenant_id=tenant_id, customer_id=customer.id, currency="USD", type="bonus")
    reader = Device(
        tenant_id=tenant_id,
        name="Pilot reader",
        type="reader",
        status="active",
        hmac_secret_encrypted=encrypt_device_secret("reader-secret"),
    )
    card = Card(
        tenant_id=tenant_id,
        uid="ARCADE-CARD",
        customer_id=customer.id,
        status="active",
        type="rfid",
    )
    db_session.add_all([paid, bonus, reader, card])
    await db_session.commit()
    for wallet, amount in ((paid, 1000), (bonus, 250)):
        await LedgerService().topup(
            db_session,
            tenant_id,
            wallet.id,
            WalletTopupRequest(amount_minor=amount, currency="USD", idempotency_key=uuid4()),
        )
    return {
        "tenant_id": tenant_id,
        "customer_id": customer.id,
        "paid_id": paid.id,
        "bonus_id": bonus.id,
        "device_id": reader.id,
        "card_id": card.id,
        "secret": "reader-secret",
        "card_uid": card.uid,
    }


async def create_machine(client, headers, env):
    response = await client.post(
        f"{ADMIN}/machines",
        headers=headers,
        json={
            "name": "Racing",
            "device_id": str(env["device_id"]),
            "price_minor": 300,
            "currency": "USD",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def play(client, signer, env, key=None):
    headers, body = signer(
        str(env["device_id"]),
        env["secret"],
        "POST",
        f"{DEVICE}/plays",
        {"card_uid": env["card_uid"], "idempotency_key": str(key or uuid4())},
    )
    return await client.post(f"{DEVICE}/plays", headers=headers, content=body)


class TestArcadePlay:
    async def test_bonus_first_and_definitive_failure_refunds_once(
        self, client, db_session, auth_headers_admin, arcade_env, device_v2_signer
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        key = uuid4()
        response = await play(client, device_v2_signer, arcade_env, key)
        assert response.status_code == 201, response.text
        result = response.json()
        allocations = list(
            (
                await db_session.execute(
                    select(TransactionAllocation)
                    .where(TransactionAllocation.transaction_id == UUID(result["transaction_id"]))
                    .order_by(TransactionAllocation.wallet_type)
                )
            ).scalars()
        )
        assert {a.wallet_type: a.amount_minor for a in allocations} == {"bonus": 250, "credit": 50}
        repeated = await play(client, device_v2_signer, arcade_env, key)
        assert repeated.json()["id"] == result["id"]
        path = f"{DEVICE}/plays/{result['id']}/outcome"
        for _ in range(2):
            headers, body = device_v2_signer(
                str(arcade_env["device_id"]),
                arcade_env["secret"],
                "POST",
                path,
                {"outcome": "failed"},
            )
            refunded = await client.post(path, headers=headers, content=body)
            assert refunded.status_code == 200, refunded.text
            assert refunded.json()["status"] == "refunded"
        for wallet_id, amount in ((arcade_env["paid_id"], 1000), (arcade_env["bonus_id"], 250)):
            wallet = await db_session.get(Wallet, wallet_id, populate_existing=True)
            assert wallet.balance_minor == amount

    async def test_unknown_play_requires_manager_for_refund(
        self, client, auth_headers_admin, arcade_env, device_v2_signer
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        response = await play(client, device_v2_signer, arcade_env)
        play_id = response.json()["id"]
        path = f"{DEVICE}/plays/{play_id}/outcome"
        for outcome, expected in (("unknown", 200), ("failed", 409)):
            headers, body = device_v2_signer(
                str(arcade_env["device_id"]),
                arcade_env["secret"],
                "POST",
                path,
                {"outcome": outcome},
            )
            assert (await client.post(path, headers=headers, content=body)).status_code == expected
        resolved = await client.post(
            f"{ADMIN}/plays/{play_id}/resolve",
            headers=auth_headers_admin,
            json={"outcome": "refunded", "reason": "Confirmed no activation"},
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["status"] == "refunded"

    async def test_partial_refunds_restore_exact_original_buckets(
        self, client, db_session, auth_headers_admin, arcade_env, device_v2_signer
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        posted = (await play(client, device_v2_signer, arcade_env)).json()
        path = f"{DEVICE}/plays/{posted['id']}/outcome"
        headers, body = device_v2_signer(
            str(arcade_env["device_id"]),
            arcade_env["secret"],
            "POST",
            path,
            {"outcome": "activated"},
        )
        assert (await client.post(path, headers=headers, content=body)).status_code == 200
        service = LedgerService()
        for amount in (1, 49, 125, 125):
            await service.refund(
                db_session,
                arcade_env["tenant_id"],
                UUID(posted["transaction_id"]),
                uuid4(),
                amount,
                "Partial recovery",
            )
        for wallet_id, expected in ((arcade_env["paid_id"], 1000), (arcade_env["bonus_id"], 250)):
            assert (
                await db_session.get(Wallet, wallet_id, populate_existing=True)
            ).balance_minor == expected


class TestFinancialReservations:
    async def test_transfer_cannot_spend_active_hold(self, db_session, arcade_env):
        tenant = arcade_env["tenant_id"]
        other = Customer(tenant_id=tenant)
        db_session.add(other)
        await db_session.flush()
        target = Wallet(tenant_id=tenant, customer_id=other.id, currency="USD", type="credit")
        db_session.add(target)
        await db_session.commit()
        ledger = LedgerService()
        await ledger.preauth(
            db_session,
            tenant,
            arcade_env["paid_id"],
            amount_minor=800,
            currency="USD",
            idempotency_key=uuid4(),
        )

        with pytest.raises(InsufficientFundsError, match="Insufficient funds"):
            await ledger.transfer(
                db_session,
                tenant,
                WalletTransferRequest(
                    from_wallet_id=arcade_env["paid_id"],
                    to_wallet_id=target.id,
                    amount_minor=500,
                    currency="USD",
                    idempotency_key=uuid4(),
                ),
            )


class TestCashierOperations:
    async def test_receipt_and_package_credit_are_atomic_and_replay_safe(
        self, client, db_session, auth_headers_admin, arcade_env
    ):
        shift = await client.post(
            f"{ADMIN}/shifts",
            headers=auth_headers_admin,
            json={"terminal": "front-desk", "opening_minor": 100, "currency": "USD"},
        )
        assert shift.status_code == 201, shift.text
        package = await client.post(
            f"{ADMIN}/topup-packages",
            headers=auth_headers_admin,
            json={"name": "Starter", "paid_minor": 1000, "bonus_minor": 200, "currency": "USD"},
        )
        assert package.status_code == 201, package.text
        payload = {
            "shift_id": shift.json()["id"],
            "customer_id": str(arcade_env["customer_id"]),
            "amount_minor": 1000,
            "currency": "USD",
            "package_id": package.json()["id"],
            "idempotency_key": str(uuid4()),
        }
        first = await client.post(
            f"{ADMIN}/cashier/topups", headers=auth_headers_admin, json=payload
        )
        assert first.status_code == 201, first.text
        second = await client.post(
            f"{ADMIN}/cashier/topups", headers=auth_headers_admin, json=payload
        )
        assert first.json()["id"] == second.json()["id"]
        count = (await db_session.execute(select(func.count()).select_from(Receipt))).scalar_one()
        assert count == 1
        closed = await client.post(
            f"{ADMIN}/shifts/{shift.json()['id']}/close",
            headers=auth_headers_admin,
            json={"counted_minor": 1100},
        )
        assert closed.status_code == 200, closed.text
        assert closed.json()["variance_minor"] == 0

    async def test_cashier_cannot_manage_users_or_adjust_wallets(
        self, client, db_session, arcade_env
    ):
        await OperationsService().roles(db_session)
        role = (await db_session.execute(select(Role).where(Role.name == "cashier"))).scalar_one()
        user = User(
            tenant_id=arcade_env["tenant_id"],
            email="cashier@example.test",
            hashed_password=hash_password("cashier-password"),
            role_id=role.id,
        )
        db_session.add(user)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}
        assert (await client.get(f"{ADMIN}/customers", headers=headers)).status_code == 200
        assert (await client.get(f"{ADMIN}/org/users", headers=headers)).status_code == 403
        adjusted = await client.post(
            f"{ADMIN}/wallets/{arcade_env['paid_id']}/topup",
            headers=headers,
            json={"amount_minor": 100, "currency": "USD", "idempotency_key": str(uuid4())},
        )
        assert adjusted.status_code == 403


class TestReporting:
    async def test_overview_counts_all_wallets_and_currencies(
        self, client, db_session, auth_headers_admin, arcade_env
    ):
        for index in range(105):
            customer = Customer(tenant_id=arcade_env["tenant_id"], full_name=f"Player {index}")
            db_session.add(customer)
            await db_session.flush()
            db_session.add(
                Wallet(
                    tenant_id=arcade_env["tenant_id"],
                    customer_id=customer.id,
                    balance_minor=1,
                    currency="USD",
                    type="credit",
                )
            )
        db_session.add(
            Wallet(
                tenant_id=arcade_env["tenant_id"],
                customer_id=arcade_env["customer_id"],
                balance_minor=100,
                currency="JPY",
                type="credit",
            )
        )
        await db_session.commit()
        response = await client.get(f"{ADMIN}/overview", headers=auth_headers_admin)
        assert response.status_code == 200, response.text
        data = {row["currency"]: row for row in response.json()["currencies"]}
        assert data["USD"]["paid_balance_minor"] == 1105
        assert data["USD"]["bonus_balance_minor"] == 250
        assert data["JPY"]["paid_balance_minor"] == 100
        assert data["JPY"]["exponent"] == 0
        assert response.json()["reconciliation_state"] == "not_checked"

    async def test_customer_search_reaches_beyond_first_page(
        self, client, auth_headers_admin, arcade_env
    ):
        response = await client.get(f"{ADMIN}/customers?q=Arcade", headers=auth_headers_admin)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1


class TestCustomerPortal:
    async def test_invitation_session_and_production_payment_boundary(
        self, client, auth_headers_admin, arcade_env, monkeypatch
    ):
        invite = await client.post(
            f"{ADMIN}/customers/{arcade_env['customer_id']}/portal-invitation",
            headers=auth_headers_admin,
            json={"email": "player@example.test"},
        )
        assert invite.status_code == 200, invite.text
        payload = {
            "invitation_token": invite.json()["invitation_token"],
            "password": "a-long-player-password",
        }
        enrolled = await client.post(f"{CUSTOMER}/auth/enroll", json=payload)
        assert enrolled.status_code == 200, enrolled.text
        headers = {"Authorization": f"Bearer {enrolled.json()['access_token']}"}
        assert (await client.get(f"{CUSTOMER}/me", headers=headers)).status_code == 200
        assert (await client.get(f"{ADMIN}/customers", headers=headers)).status_code == 401
        assert (await client.get(f"{CUSTOMER}/me", headers=auth_headers_admin)).status_code == 401
        assert (await client.post(f"{CUSTOMER}/auth/enroll", json=payload)).status_code == 401
        monkeypatch.setattr(settings, "payment_provider", "sandbox")
        monkeypatch.setattr(settings, "environment", "production")
        response = await client.post(
            f"{CUSTOMER}/payments/checkouts",
            headers=headers,
            json={"amount_minor": 100, "currency": "USD", "idempotency_key": str(uuid4())},
        )
        assert response.status_code == 503


class TestPilotRecovery:
    async def test_region_validation_and_machine_outcomes_require_hmac_v2(
        self, client, auth_headers_admin, arcade_env, device_v2_signer, device_signer
    ):
        invalid = await client.patch(
            f"{ADMIN}/org/settings", headers=auth_headers_admin, json={"timezone": "Mars/Space"}
        )
        assert invalid.status_code == 422
        await create_machine(client, auth_headers_admin, arcade_env)
        result = (await play(client, device_v2_signer, arcade_env)).json()
        path = f"{DEVICE}/plays/{result['id']}/outcome"
        headers, body = device_signer(str(arcade_env["device_id"]), {"outcome": "failed"})
        denied = await client.post(path, headers=headers, content=body)
        assert denied.status_code == 403, denied.text

    async def test_staff_revocation_and_reader_credentials_permission(
        self, client, db_session, auth_headers_admin, arcade_env
    ):
        roles = await OperationsService().roles(db_session)
        technician = next(row for row in roles if row["name"] == "technician")
        user = User(
            tenant_id=arcade_env["tenant_id"],
            email="tech@pilot.test",
            hashed_password=hash_password("technician-test-password"),
            role_id=technician["id"],
        )
        db_session.add(user)
        await db_session.commit()
        login = await client.post(
            f"{ADMIN}/auth/login",
            json={"email": user.email, "password": "technician-test-password"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert (await client.get(f"{ADMIN}/devices", headers=headers)).status_code == 200
        secret = await client.post(
            f"{ADMIN}/devices/{arcade_env['device_id']}/credentials/rotate", headers=headers
        )
        assert secret.status_code == 403
        policy = await client.put(
            f"{ADMIN}/offline/policy", headers=headers, json={"enabled": False}
        )
        assert policy.status_code == 403
        disabled = await client.patch(
            f"{ADMIN}/org/users/{user.id}", headers=auth_headers_admin, json={"status": "inactive"}
        )
        assert disabled.status_code == 200, disabled.text
        assert (await client.get(f"{ADMIN}/devices", headers=headers)).status_code == 403
        restored = await client.patch(
            f"{ADMIN}/org/users/{user.id}", headers=auth_headers_admin, json={"status": "active"}
        )
        assert restored.status_code == 200
        assert (await client.get(f"{ADMIN}/devices", headers=headers)).status_code == 401

    async def test_guardian_funds_child_without_transferring_bonus_or_allowing_self_limit_change(
        self, client, db_session, auth_headers_admin, arcade_env
    ):
        child = Customer(tenant_id=arcade_env["tenant_id"], full_name="Child")
        db_session.add(child)
        await db_session.commit()
        link = await client.post(
            f"{ADMIN}/families",
            headers=auth_headers_admin,
            json={"guardian_id": str(arcade_env["customer_id"]), "child_id": str(child.id)},
        )
        assert link.status_code == 201, link.text

        async def enroll(customer_id, email):
            invite = await client.post(
                f"{ADMIN}/customers/{customer_id}/portal-invitation",
                headers=auth_headers_admin,
                json={"email": email},
            )
            result = await client.post(
                f"{CUSTOMER}/auth/enroll",
                json={
                    "invitation_token": invite.json()["invitation_token"],
                    "password": "family-test-password",
                },
            )
            assert result.status_code == 200, result.text
            return {"Authorization": f"Bearer {result.json()['access_token']}"}

        parent_headers = await enroll(arcade_env["customer_id"], "guardian@example.test")
        child_headers = await enroll(child.id, "child@example.test")
        transferred = await client.post(
            f"{CUSTOMER}/family/{child.id}/fund",
            headers=parent_headers,
            json={"amount_minor": 200, "currency": "USD", "idempotency_key": str(uuid4())},
        )
        assert transferred.status_code == 200, transferred.text
        for wallet_id, expected in [(arcade_env["paid_id"], 800), (arcade_env["bonus_id"], 250)]:
            wallet = await db_session.get(Wallet, wallet_id, populate_existing=True)
            assert wallet.balance_minor == expected
        limit = {"currency": "USD", "daily_minor": 100}
        assert (
            await client.put(
                f"{CUSTOMER}/family/{child.id}/spending-limit", headers=parent_headers, json=limit
            )
        ).status_code == 200
        assert (
            await client.put(
                f"{CUSTOMER}/family/{child.id}/spending-limit", headers=child_headers, json=limit
            )
        ).status_code == 403
        assert (
            await client.get(
                f"{CUSTOMER}/accounts/{arcade_env['customer_id']}", headers=child_headers
            )
        ).status_code == 403

    async def test_bonus_only_failure_restores_funding_and_machine_report(
        self, client, db_session, auth_headers_admin, arcade_env, device_v2_signer
    ):
        machine = await create_machine(client, auth_headers_admin, arcade_env)
        changed = await client.patch(
            f"{ADMIN}/machines/{machine['id']}",
            headers=auth_headers_admin,
            json={"price_minor": 200},
        )
        assert changed.status_code == 200, changed.text
        result = (await play(client, device_v2_signer, arcade_env)).json()
        path = f"{DEVICE}/plays/{result['id']}/outcome"
        headers, body = device_v2_signer(
            str(arcade_env["device_id"]), arcade_env["secret"], "POST", path, {"outcome": "failed"}
        )
        response = await client.post(path, headers=headers, content=body)
        assert response.status_code == 200, response.text
        bonus = await db_session.get(Wallet, arcade_env["bonus_id"], populate_existing=True)
        assert bonus.balance_minor == 250
        report = await client.get(f"{ADMIN}/reports/machines", headers=auth_headers_admin)
        assert report.status_code == 200, report.text
        row = report.json()[0]
        assert (row["attempts"], row["failures"], row["refund_minor"]) == (1, 1, 200)
        assert row["net_paid_spend_minor"] == 0

    async def test_real_reader_signature_and_durable_replay(
        self, client, auth_headers_admin, arcade_env, tmp_path
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        reader = ReaderSimulator(
            client,
            arcade_env["device_id"],
            arcade_env["secret"],
            ReaderJournal(tmp_path / "reader.sqlite"),
        )
        pulses = []
        key = uuid4()
        for _ in range(2):
            result = await reader.tap(key, arcade_env["card_uid"], lambda: pulses.append(1))
            assert result["status"] == "activated"
        assert pulses == [1]

    async def test_reconciliation_pauses_then_audited_repair_and_resume(
        self, client, db_session, auth_headers_admin, arcade_env, device_v2_signer
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        wallet = await db_session.get(Wallet, arcade_env["paid_id"], populate_existing=True)
        wallet.balance_minor += 1
        await db_session.commit()
        check = await client.post(f"{ADMIN}/ledger/reconciliation/run", headers=auth_headers_admin)
        assert check.status_code == 200, check.text
        assert check.json()["healthy"] is False
        blocked = await play(client, device_v2_signer, arcade_env)
        assert blocked.status_code >= 400
        premature = await client.post(
            f"{ADMIN}/ledger/resume",
            headers=auth_headers_admin,
            json={"reason": "investigation complete"},
        )
        assert premature.status_code == 409
        repair = await client.post(
            f"{ADMIN}/ledger/repair-wallet-cache",
            headers=auth_headers_admin,
            json={"wallet_id": str(wallet.id), "reason": "verified cache drift"},
        )
        assert repair.status_code == 200, repair.text
        assert repair.json()["balance_minor"] == 1000
        resumed = await client.post(
            f"{ADMIN}/ledger/resume",
            headers=auth_headers_admin,
            json={"reason": "cache rebuilt and verified"},
        )
        assert resumed.status_code == 200, resumed.text
        assert (await play(client, device_v2_signer, arcade_env)).status_code == 201

    async def test_daily_limit_and_refund_restore_allowance(
        self, client, auth_headers_admin, arcade_env, device_v2_signer
    ):
        await create_machine(client, auth_headers_admin, arcade_env)
        limit = await client.put(
            f"{ADMIN}/customers/{arcade_env['customer_id']}/spending-limit",
            headers=auth_headers_admin,
            json={"daily_minor": 300, "currency": "USD"},
        )
        assert limit.status_code == 200, limit.text
        first = await play(client, device_v2_signer, arcade_env)
        assert first.status_code == 201
        assert (await play(client, device_v2_signer, arcade_env)).status_code == 403
        path = f"{DEVICE}/plays/{first.json()['id']}/outcome"
        headers, body = device_v2_signer(
            str(arcade_env["device_id"]), arcade_env["secret"], "POST", path, {"outcome": "failed"}
        )
        assert (await client.post(path, headers=headers, content=body)).status_code == 200
        assert (await play(client, device_v2_signer, arcade_env)).status_code == 201

    async def test_history_cursor_and_filtered_authenticated_export(
        self, client, db_session, auth_headers_admin, arcade_env, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(settings, "export_directory", str(tmp_path))
        first = await client.get(
            f"{ADMIN}/transactions/history?limit=1", headers=auth_headers_admin
        )
        assert first.status_code == 200, first.text
        cursor = first.json()["next_cursor"]
        assert cursor
        second = await client.get(
            f"{ADMIN}/transactions/history",
            headers=auth_headers_admin,
            params={"limit": 1, "cursor": cursor},
        )
        assert second.status_code == 200, second.text
        assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
        changed = await client.get(
            f"{ADMIN}/transactions/history",
            headers=auth_headers_admin,
            params={"currency": "EUR", "cursor": cursor},
        )
        assert changed.status_code == 422
        job = await client.post(
            f"{ADMIN}/exports",
            headers=auth_headers_admin,
            json={
                "idempotency_key": str(uuid4()),
                "format": "csv",
                "filters": {"wallet_id": str(arcade_env["paid_id"])},
            },
        )
        assert job.status_code == 202, job.text
        await ExportService().process(db_session, UUID(job.json()["id"]))
        download = await client.get(
            f"{ADMIN}/exports/{job.json()['id']}/download", headers=auth_headers_admin
        )
        assert download.status_code == 200, download.text

        rows = list(csv.DictReader(io.StringIO(download.text)))
        assert [int(row["amount_minor"]) for row in rows] == [1000]
        assert (await client.get(f"{ADMIN}/exports/{job.json()['id']}/download")).status_code == 401

    async def test_scheduled_price_snapshot_survives_price_change(
        self, client, auth_headers_admin, arcade_env, device_v2_signer
    ):
        machine = await create_machine(client, auth_headers_admin, arcade_env)
        schedule = {
            "machine_id": machine["id"],
            "name": "Happy hour",
            "weekday": datetime.now(UTC).weekday(),
            "start_minute": 0,
            "end_minute": 1440,
            "price_minor": 150,
        }
        added = await client.post(
            f"{ADMIN}/pricing-schedules", headers=auth_headers_admin, json=schedule
        )
        assert added.status_code == 201, added.text
        overlap = await client.post(
            f"{ADMIN}/pricing-schedules", headers=auth_headers_admin, json=schedule
        )
        assert overlap.status_code == 409
        key = uuid4()
        first = await play(client, device_v2_signer, arcade_env, key)
        assert first.json()["amount_minor"] == 150
        await client.patch(
            f"{ADMIN}/machines/{machine['id']}",
            headers=auth_headers_admin,
            json={"price_minor": 900},
        )
        repeated = await play(client, device_v2_signer, arcade_env, key)
        assert repeated.json()["price_snapshot"] == first.json()["price_snapshot"]

    async def test_sandbox_checkout_credits_once(
        self, client, db_session, auth_headers_admin, arcade_env, monkeypatch
    ):
        monkeypatch.setattr(settings, "payment_provider", "sandbox")
        invite = await client.post(
            f"{ADMIN}/customers/{arcade_env['customer_id']}/portal-invitation",
            headers=auth_headers_admin,
            json={"email": "sandbox@example.test"},
        )
        enrolled = await client.post(
            f"{CUSTOMER}/auth/enroll",
            json={
                "invitation_token": invite.json()["invitation_token"],
                "password": "sandbox-player-password",
            },
        )
        headers = {"Authorization": f"Bearer {enrolled.json()['access_token']}"}
        created = await client.post(
            f"{CUSTOMER}/payments/checkouts",
            headers=headers,
            json={"amount_minor": 100, "currency": "USD", "idempotency_key": str(uuid4())},
        )
        assert created.status_code == 201, created.text
        for _ in range(2):
            paid = await client.post(
                f"{CUSTOMER}/payments/checkouts/{created.json()['session_id']}/simulate",
                headers=headers,
            )
            assert paid.status_code == 200, paid.text
        wallet = await db_session.get(Wallet, arcade_env["paid_id"], populate_existing=True)
        assert wallet.balance_minor == 1100
