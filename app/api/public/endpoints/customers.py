# app/api/public/endpoints/customers.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import ApiKeyContext, rate_limit_public, require_scope
from app.core.scopes import PII_SCOPE, PublicScope
from app.models.ledger.wallet import Customer
from app.schemas.customer import CustomerCreate
from app.schemas.public import (
    PaginatedPublicCustomerOut,
    PublicBalancesOut,
    PublicCustomerCreate,
    PublicCustomerOut,
    PublicWalletBalanceOut,
)
from app.services.customer import CustomerService

router = APIRouter(
    prefix="/customers",
    tags=["public-customers"],
    dependencies=[Depends(rate_limit_public)],
)


def _serialize_customer(customer: Customer, ctx: ApiKeyContext) -> PublicCustomerOut:
    """Redact PII (email/phone) unless the key holds the elevated scope."""
    show_pii = ctx.has_scope(PII_SCOPE)
    return PublicCustomerOut(
        id=customer.id,
        external_id=customer.external_id,
        full_name=customer.full_name,
        email=customer.email if show_pii else None,
        phone=customer.phone if show_pii else None,
        status=customer.status,
    )


@router.get("", response_model=PaginatedPublicCustomerOut)
async def list_customers(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CUSTOMERS_READ))],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedPublicCustomerOut:
    """List customers for the API key's tenant (contact fields redacted)."""
    result = await CustomerService().list_customers(db, ctx.tenant_id, page, limit)
    items = [_serialize_customer(c, ctx) for c in result["items"]]
    return PaginatedPublicCustomerOut(
        page=result["page"], total=result["total"], pages=result["pages"], items=items
    )


@router.post("", response_model=PublicCustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: PublicCustomerCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CUSTOMERS_WRITE))],
) -> PublicCustomerOut:
    """Create a customer for the API key's tenant."""
    customer = await CustomerService().create_customer(
        db, ctx.tenant_id, CustomerCreate(**payload.model_dump())
    )
    return _serialize_customer(customer, ctx)


@router.get("/{customer_id}", response_model=PublicCustomerOut)
async def get_customer(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CUSTOMERS_READ))],
) -> PublicCustomerOut:
    """Get a single customer (contact fields redacted unless elevated)."""
    customer = await CustomerService().get_customer(db, ctx.tenant_id, customer_id)
    return _serialize_customer(customer, ctx)


@router.get("/{customer_id}/balances", response_model=PublicBalancesOut)
async def get_customer_balances(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    ctx: Annotated[ApiKeyContext, Depends(require_scope(PublicScope.CUSTOMERS_READ))],
) -> PublicBalancesOut:
    """Return the customer's wallet balances."""
    wallets = await CustomerService().get_balances(db, ctx.tenant_id, customer_id)
    return PublicBalancesOut(
        balances=[
            PublicWalletBalanceOut(
                wallet_id=w.id,
                currency=w.currency,
                balance_minor=w.balance_minor,
                type=w.type,
            )
            for w in wallets
        ]
    )
