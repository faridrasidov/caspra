from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID, uuid4

from jwt import PyJWTError as JWTError
from sqlalchemy import select, update

from app.core.domain_errors import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.device.device import Card
from app.models.identity.customer import CustomerIdentity, CustomerSession
from app.models.ledger.wallet import Customer
from app.models.tenant.organization import Organization
from app.models.tenant.venue import FamilyRelationship
from app.schemas.arcade import PortalToken
from app.schemas.wallet import WalletTransferRequest
from app.services.ledger import LedgerService
from app.services.venue import VenueService


class CustomerPortalService(VenueService):
    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def aware(value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    async def invite(self, db, tenant_id, customer_id, email):
        await self.owned(db, Customer, tenant_id, customer_id, lock=True)
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise ValidationError("Enter a valid email")
        duplicate = (
            await db.execute(
                select(CustomerIdentity).where(
                    CustomerIdentity.tenant_id == tenant_id, CustomerIdentity.email == normalized
                )
            )
        ).scalar_one_or_none()
        if duplicate and duplicate.customer_id != customer_id:
            raise ConflictError("Email already belongs to another customer")
        identity = (
            await db.execute(
                select(CustomerIdentity).where(
                    CustomerIdentity.tenant_id == tenant_id,
                    CustomerIdentity.customer_id == customer_id,
                )
            )
        ).scalar_one_or_none()
        if identity is None:
            identity = CustomerIdentity(
                tenant_id=tenant_id, customer_id=customer_id, email=normalized
            )
            db.add(identity)
        raw = secrets.token_urlsafe(48)
        identity.email = normalized
        identity.invitation_hash = self.digest(raw)
        identity.invitation_expires_at = datetime.now(UTC) + timedelta(hours=24)
        # Recovery immediately revokes existing sessions, and tokens never enter audit payloads.
        if identity.id:
            await db.execute(
                update(CustomerSession)
                .where(CustomerSession.identity_id == identity.id)
                .values(revoked=True)
            )
        await db.commit()
        return {"invitation_token": raw, "expires_at": identity.invitation_expires_at}

    async def enroll(self, db, payload):
        identity = (
            await db.execute(
                select(CustomerIdentity)
                .where(CustomerIdentity.invitation_hash == self.digest(payload.invitation_token))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if (
            identity is None
            or identity.invitation_expires_at is None
            or self.aware(identity.invitation_expires_at) <= datetime.now(UTC)
        ):
            raise UnauthorizedError("Invitation is invalid or expired")
        identity.hashed_password = hash_password(payload.password)
        identity.invitation_hash = None
        identity.invitation_expires_at = None
        identity.active = True
        await db.execute(
            update(CustomerSession)
            .where(CustomerSession.identity_id == identity.id)
            .values(revoked=True)
        )
        tokens = await self.issue_session(db, identity)
        await db.commit()
        return tokens

    async def login(self, db, payload):
        org = (
            await db.execute(select(Organization).where(Organization.slug == payload.tenant_slug))
        ).scalar_one_or_none()
        identity = None
        if org:
            identity = (
                await db.execute(
                    select(CustomerIdentity).where(
                        CustomerIdentity.tenant_id == org.id,
                        CustomerIdentity.email == payload.email.strip().lower(),
                    )
                )
            ).scalar_one_or_none()
        if (
            identity is None
            or not identity.active
            or not identity.hashed_password
            or not verify_password(payload.password, identity.hashed_password)
        ):
            raise UnauthorizedError("Invalid credentials")
        customer = await self.owned(db, Customer, identity.tenant_id, identity.customer_id)
        if customer.status != "active" or org.status != "active":
            raise UnauthorizedError("Account is not active")
        tokens = await self.issue_session(db, identity)
        await db.commit()
        return tokens

    async def issue_session(self, db, identity, family_id=None):
        raw = secrets.token_urlsafe(48)
        row = CustomerSession(
            tenant_id=identity.tenant_id,
            identity_id=identity.id,
            token_hash=self.digest(raw),
            family_id=family_id or uuid4(),
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.add(row)
        await db.flush()
        return PortalToken(
            access_token=create_access_token(
                str(identity.id), audience="customer", session_id=str(row.id)
            )
        ), raw

    async def refresh(self, db, raw):
        row = (
            await db.execute(
                select(CustomerSession)
                .where(CustomerSession.token_hash == self.digest(raw))
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise UnauthorizedError("Invalid refresh token")
        if row.revoked or self.aware(row.expires_at) <= datetime.now(UTC):
            await db.execute(
                update(CustomerSession)
                .where(CustomerSession.family_id == row.family_id)
                .values(revoked=True)
            )
            await db.commit()
            raise UnauthorizedError("Session expired or refresh token reused")
        identity = await db.get(CustomerIdentity, row.identity_id)
        if identity is None or not identity.active:
            raise UnauthorizedError("Account is not active")
        customer = await self.owned(db, Customer, row.tenant_id, identity.customer_id)
        if not identity.active or customer.status != "active":
            raise UnauthorizedError("Account is not active")
        row.revoked = True
        tokens = await self.issue_session(db, identity, row.family_id)
        await db.commit()
        return tokens

    async def authenticate(self, db, token):
        try:
            claims = decode_access_token(token, audience="customer")
            identity_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
        except (ValueError, KeyError, TypeError, JWTError) as exc:
            # The token decoder's JWTError and malformed UUIDs share the same boundary.
            raise UnauthorizedError("Invalid customer token") from exc
        identity = await db.get(CustomerIdentity, identity_id)
        row = await db.get(CustomerSession, session_id)
        if (
            identity is None
            or not identity.active
            or row is None
            or row.identity_id != identity.id
            or row.revoked
            or self.aware(row.expires_at) <= datetime.now(UTC)
        ):
            raise UnauthorizedError("Customer session is not active")
        customer = await self.owned(db, Customer, identity.tenant_id, identity.customer_id)
        org = await db.get(Organization, identity.tenant_id)
        if customer.status != "active" or org.status != "active":
            raise ForbiddenError("Account is not active")
        return identity

    async def logout(self, db, identity):
        await db.execute(
            update(CustomerSession)
            .where(CustomerSession.identity_id == identity.id)
            .values(revoked=True)
        )
        await db.commit()

    async def assert_access(self, db, identity, customer_id):
        if identity.customer_id == customer_id:
            return
        linked = (
            await db.execute(
                select(FamilyRelationship.id).where(
                    FamilyRelationship.tenant_id == identity.tenant_id,
                    FamilyRelationship.guardian_id == identity.customer_id,
                    FamilyRelationship.child_id == customer_id,
                )
            )
        ).first()
        if linked is None:
            raise ForbiddenError("Customer is not linked to this account")

    async def family(self, db, identity):
        return list(
            (
                await db.execute(
                    select(FamilyRelationship).where(
                        FamilyRelationship.tenant_id == identity.tenant_id,
                        FamilyRelationship.guardian_id == identity.customer_id,
                    )
                )
            ).scalars()
        )

    async def block_card(self, db, identity, card_id):
        card = await self.owned(db, Card, identity.tenant_id, card_id, lock=True)
        await self.assert_access(db, identity, card.customer_id)
        card.status = "lost"
        await db.commit()
        return card

    async def family_fund(self, db, identity, child_id, payload):
        if child_id == identity.customer_id:
            raise ValidationError("Choose a linked child")
        await self.assert_access(db, identity, child_id)
        for cid in sorted([identity.customer_id, child_id], key=str):
            await self.owned(db, Customer, identity.tenant_id, cid, lock=True)
        source = await self.funding_wallet(
            db, identity.tenant_id, identity.customer_id, payload.currency, "credit"
        )
        target = await self.funding_wallet(
            db, identity.tenant_id, child_id, payload.currency, "credit"
        )
        return await LedgerService().transfer(
            db,
            identity.tenant_id,
            WalletTransferRequest(
                from_wallet_id=source.id,
                to_wallet_id=target.id,
                amount_minor=payload.amount_minor,
                currency=payload.currency,
                idempotency_key=payload.idempotency_key,
            ),
        )
