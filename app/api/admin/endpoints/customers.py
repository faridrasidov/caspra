# app/api/admin/endpoints/customers.py

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_admin
from app.models.identity.user import User
from app.schemas.customer import (
    CustomerBalancesOut,
    CustomerCreate,
    CustomerImportRequest,
    CustomerImportResult,
    CustomerOut,
    CustomerUpdate,
    PaginatedCustomerOut,
    WalletBalanceOut,
)
from app.services.customer import CustomerService

router = APIRouter(prefix="/customers", tags=["admin-customers"])


@router.get("", response_model=PaginatedCustomerOut)
async def list_customers(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedCustomerOut:
    """List customers for the caller's tenant."""
    result = await CustomerService().list_customers(db, current_admin.tenant_id, page, limit)
    return PaginatedCustomerOut(**result)


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: CustomerCreate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CustomerOut:
    """Create a customer for the caller's tenant."""
    return await CustomerService().create_customer(db, current_admin.tenant_id, payload)


@router.post("/import", response_model=CustomerImportResult)
async def import_customers(
    payload: CustomerImportRequest,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CustomerImportResult:
    """Bulk-import customers, skipping duplicates by external_id."""
    return await CustomerService().import_customers(db, current_admin.tenant_id, payload)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CustomerOut:
    """Get a single customer."""
    return await CustomerService().get_customer(db, current_admin.tenant_id, customer_id)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CustomerOut:
    """Update a customer."""
    return await CustomerService().update_customer(
        db, current_admin.tenant_id, customer_id, payload
    )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> None:
    """Delete a customer."""
    await CustomerService().delete_customer(db, current_admin.tenant_id, customer_id)


@router.get("/{customer_id}/balances", response_model=CustomerBalancesOut)
async def get_customer_balances(
    customer_id: UUID,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[User, Depends(get_current_admin)],
) -> CustomerBalancesOut:
    """Return the customer's wallet balances."""
    wallets = await CustomerService().get_balances(db, current_admin.tenant_id, customer_id)
    balances = [
        WalletBalanceOut(
            wallet_id=w.id,
            currency=w.currency,
            balance_minor=w.balance_minor,
            type=w.type,
        )
        for w in wallets
    ]
    return CustomerBalancesOut(customer_id=customer_id, balances=balances)
