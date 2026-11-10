from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme, get_db
from app.core.config import settings
from app.core.domain_errors import DomainError, ForbiddenError, UnauthorizedError
from app.core.rate_limit import check_login_rate_limit
from app.models.identity.customer import CustomerIdentity
from app.models.tenant.venue import TopupPackage
from app.schemas.arcade import (
    CheckoutOut,
    CheckoutRequest,
    CustomerWorkspace,
    FamilyFunding,
    FamilyOut,
    LimitOut,
    LimitUpdate,
    PackageOut,
    Page,
    PortalEnroll,
    PortalLogin,
    PortalToken,
)
from app.schemas.card import CardOut
from app.schemas.transaction import TransactionOut
from app.services.customer_portal import CustomerPortalService
from app.services.payments import PaymentService

router = APIRouter(tags=["customer-portal"])
DB = Annotated[AsyncSession, Depends(get_db)]
COOKIE = "caspra_customer_refresh"


async def current_customer(
    db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
):
    if credentials is None:
        raise UnauthorizedError("Customer login required")
    return await CustomerPortalService().authenticate(db, credentials.credentials)


Customer = Annotated[CustomerIdentity, Depends(current_customer)]


def set_cookie(response, raw):
    response.set_cookie(
        COOKIE,
        raw,
        httponly=True,
        secure=settings.environment == "production",
        samesite="strict",
        path=f"{settings.customer_api_prefix}/auth",
        max_age=30 * 24 * 3600,
    )


@router.post("/auth/enroll", response_model=PortalToken)
async def enroll(payload: PortalEnroll, request: Request, response: Response, db: DB):
    await check_login_rate_limit(
        request.client.host if request.client else "unknown", "customer-enrollment"
    )
    token, raw = await CustomerPortalService().enroll(db, payload)
    set_cookie(response, raw)
    return token


@router.post("/auth/login", response_model=PortalToken)
async def login(payload: PortalLogin, request: Request, response: Response, db: DB):
    await check_login_rate_limit(
        request.client.host if request.client else "unknown",
        f"customer:{payload.tenant_slug}:{payload.email}",
    )
    token, raw = await CustomerPortalService().login(db, payload)
    set_cookie(response, raw)
    return token


@router.post("/auth/refresh", response_model=PortalToken)
async def refresh(request: Request, response: Response, db: DB):
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise UnauthorizedError("Refresh cookie required")
    token, replacement = await CustomerPortalService().refresh(db, raw)
    set_cookie(response, replacement)
    return token


@router.post("/auth/logout", status_code=204)
async def logout(response: Response, db: DB, identity: Customer):
    await CustomerPortalService().logout(db, identity)
    response.delete_cookie(COOKIE, path=f"{settings.customer_api_prefix}/auth")


@router.get("/me", response_model=CustomerWorkspace)
async def me(db: DB, identity: Customer):
    return await CustomerPortalService().customer_workspace(
        db, identity.tenant_id, identity.customer_id
    )


@router.get("/accounts/{customer_id}", response_model=CustomerWorkspace)
async def account(customer_id: UUID, db: DB, identity: Customer):
    service = CustomerPortalService()
    await service.assert_access(db, identity, customer_id)
    return await service.customer_workspace(db, identity.tenant_id, customer_id)


@router.get("/family", response_model=list[FamilyOut])
async def family(db: DB, identity: Customer):
    return await CustomerPortalService().family(db, identity)


@router.post("/family/{child_id}/fund", response_model=TransactionOut)
async def fund_child(child_id: UUID, payload: FamilyFunding, db: DB, identity: Customer):
    return await CustomerPortalService().family_fund(db, identity, child_id, payload)


@router.put("/family/{child_id}/spending-limit", response_model=LimitOut)
async def child_limit(child_id: UUID, payload: LimitUpdate, db: DB, identity: Customer):
    if child_id == identity.customer_id:
        raise ForbiddenError("Only guardians can change a child's allowance")
    service = CustomerPortalService()
    await service.assert_access(db, identity, child_id)
    return await service.set_limit(db, identity.tenant_id, child_id, payload)


@router.post("/cards/{card_id}/block", response_model=CardOut)
async def block_card(card_id: UUID, db: DB, identity: Customer):
    return await CustomerPortalService().block_card(db, identity, card_id)


@router.get("/topup-packages", response_model=Page[PackageOut])
async def packages(db: DB, identity: Customer):
    return await CustomerPortalService().list_records(
        db, TopupPackage, identity.tenant_id, 1, 100, filters=(TopupPackage.active.is_(True),)
    )


@router.get("/payments/status", response_model=dict[str, bool])
async def payment_status(db: DB, identity: Customer):
    try:
        await PaymentService().adapter(db, identity)
    except DomainError:
        return {"available": False, "sandbox": False}
    return {"available": True, "sandbox": True}


@router.post("/payments/checkouts", response_model=CheckoutOut, status_code=201)
async def checkout(payload: CheckoutRequest, db: DB, identity: Customer):
    return await PaymentService().create(db, identity, payload)


@router.post("/payments/checkouts/{checkout_id}/simulate", response_model=CheckoutOut)
async def sandbox_payment(checkout_id: UUID, db: DB, identity: Customer):
    return await PaymentService().simulate(db, identity, checkout_id)
