# app/services/customer.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain_errors import ConflictError
from app.models.ledger.wallet import Customer, Wallet
from app.schemas.customer import (
    CustomerCreate,
    CustomerImportRequest,
    CustomerImportResult,
    CustomerUpdate,
)
from app.services.base import TenantScopedService


class CustomerService(TenantScopedService):
    """Manage tenant-scoped end-user cardholders."""

    model = Customer
    resource_name = "Customer"

    async def list_customers(
        self, db: AsyncSession, tenant_id: UUID, page: int, limit: int
    ) -> dict:
        return await self.paginate(db, tenant_id, page, limit, order_by=Customer.created_at.desc())

    async def create_customer(
        self, db: AsyncSession, tenant_id: UUID, payload: CustomerCreate
    ) -> Customer:
        await self._assert_external_id_free(db, tenant_id, payload.external_id)
        customer = Customer(tenant_id=tenant_id, **payload.model_dump())
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        return customer

    async def import_customers(
        self, db: AsyncSession, tenant_id: UUID, payload: CustomerImportRequest
    ) -> CustomerImportResult:
        created = 0
        skipped = 0
        for entry in payload.customers:
            if entry.external_id is not None:
                stmt = select(Customer.id).where(
                    Customer.tenant_id == tenant_id,
                    Customer.external_id == entry.external_id,
                )
                if (await db.execute(stmt)).first() is not None:
                    skipped += 1
                    continue
            db.add(Customer(tenant_id=tenant_id, **entry.model_dump()))
            created += 1
        await db.commit()
        return CustomerImportResult(created=created, skipped=skipped)

    async def get_customer(self, db: AsyncSession, tenant_id: UUID, customer_id: UUID) -> Customer:
        return await self.get_owned(db, customer_id, tenant_id)

    async def update_customer(
        self, db: AsyncSession, tenant_id: UUID, customer_id: UUID, payload: CustomerUpdate
    ) -> Customer:
        customer = await self.get_owned(db, customer_id, tenant_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(customer, key, value.value if hasattr(value, "value") else value)
        await db.commit()
        await db.refresh(customer)
        return customer

    async def delete_customer(self, db: AsyncSession, tenant_id: UUID, customer_id: UUID) -> None:
        customer = await self.get_owned(db, customer_id, tenant_id)
        await db.delete(customer)
        await db.commit()

    async def get_balances(
        self, db: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> list[Wallet]:
        await self.get_owned(db, customer_id, tenant_id)
        stmt = select(Wallet).where(
            Wallet.tenant_id == tenant_id, Wallet.customer_id == customer_id
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _assert_external_id_free(
        self, db: AsyncSession, tenant_id: UUID, external_id: str | None
    ) -> None:
        if external_id is None:
            return
        stmt = select(Customer.id).where(
            Customer.tenant_id == tenant_id, Customer.external_id == external_id
        )
        if (await db.execute(stmt)).first() is not None:
            raise ConflictError(f"Customer with external_id '{external_id}' already exists")
