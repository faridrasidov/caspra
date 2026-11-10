from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_snapshot_db, require_admin_permission
from app.core.admin_permissions import AdminPermission as P
from app.models.catalog.arcade import Machine, PlaySession, PricingSchedule
from app.models.identity.user import User
from app.models.tenant.venue import (
    CashierShift,
    FamilyRelationship,
    Receipt,
    TopupPackage,
)
from app.schemas.arcade import (
    AlertOut,
    CacheRepair,
    CashMovementCreate,
    CashMovementOut,
    CashTopup,
    CustomerWorkspace,
    FamilyCreate,
    FamilyOut,
    LimitOut,
    LimitUpdate,
    MachineCreate,
    MachineOut,
    MachineReportOut,
    MachineUpdate,
    OverviewOut,
    PackageCreate,
    PackageOut,
    Page,
    PlayOut,
    PlayResolution,
    PortalInvitationOut,
    PortalInvite,
    PricingScheduleCreate,
    PricingScheduleOut,
    Reason,
    ReceiptOut,
    RoleOut,
    ShiftClose,
    ShiftOpen,
    ShiftOut,
)
from app.schemas.reconciliation import ReconciliationReportOut
from app.schemas.wallet import WalletBalanceOut
from app.services.arcade import ArcadeService
from app.services.customer_portal import CustomerPortalService
from app.services.operations import OperationsService
from app.services.overview import OverviewService
from app.services.venue import VenueService

router = APIRouter(tags=["admin-arcade"])
DB = Annotated[AsyncSession, Depends(get_db)]
SnapshotDB = Annotated[AsyncSession, Depends(get_snapshot_db)]
PageNumber = Annotated[int, Query(ge=1)]
LimitNumber = Annotated[int, Query(ge=1, le=100)]
MachineReader = Annotated[User, Depends(require_admin_permission(P.MACHINES_READ))]
MachineManager = Annotated[User, Depends(require_admin_permission(P.MACHINES_MANAGE))]
PricingManager = Annotated[User, Depends(require_admin_permission(P.PRICING_MANAGE))]
PlayReader = Annotated[User, Depends(require_admin_permission(P.PLAYS_READ))]
PlayManager = Annotated[User, Depends(require_admin_permission(P.PLAYS_RESOLVE))]
Cashier = Annotated[User, Depends(require_admin_permission(P.SHIFTS_OPERATE))]
ShiftManager = Annotated[User, Depends(require_admin_permission(P.SHIFTS_REVIEW))]
FamilyManager = Annotated[User, Depends(require_admin_permission(P.FAMILY_MANAGE))]


@router.get("/overview", response_model=OverviewOut)
async def overview(
    db: SnapshotDB,
    actor: Annotated[User, Depends(require_admin_permission(P.REPORTS_READ))],
    start: date | None = None,
    end: date | None = None,
    currency: str | None = None,
    location_id: UUID | None = None,
):
    return await OverviewService().overview(
        db, actor.tenant_id, start=start, end=end, currency=currency, location_id=location_id
    )


@router.get("/machines", response_model=Page[MachineOut])
async def machines(
    db: DB,
    actor: MachineReader,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(db, Machine, actor.tenant_id, page, limit, q=q)


@router.post("/machines", response_model=MachineOut, status_code=201)
async def create_machine(payload: MachineCreate, db: DB, actor: MachineManager):
    return await ArcadeService().create_machine(db, actor.tenant_id, payload)


@router.patch("/machines/{machine_id}", response_model=MachineOut)
async def update_machine(machine_id: UUID, payload: MachineUpdate, db: DB, actor: MachineManager):
    return await ArcadeService().update_machine(db, actor.tenant_id, machine_id, payload)


@router.delete("/machines/{machine_id}", status_code=204)
async def archive_machine(machine_id: UUID, db: DB, actor: MachineManager):
    await ArcadeService().update_machine(
        db, actor.tenant_id, machine_id, MachineUpdate(state="archived")
    )


@router.get("/pricing-schedules", response_model=Page[PricingScheduleOut])
async def schedules(
    db: DB,
    actor: PricingManager,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(
        db, PricingSchedule, actor.tenant_id, page, limit, q=q
    )


@router.post("/pricing-schedules", response_model=PricingScheduleOut, status_code=201)
async def create_schedule(payload: PricingScheduleCreate, db: DB, actor: PricingManager):
    return await ArcadeService().create_schedule(db, actor.tenant_id, payload)


@router.delete("/pricing-schedules/{schedule_id}", status_code=204)
async def disable_schedule(schedule_id: UUID, db: DB, actor: PricingManager):
    await ArcadeService().disable_schedule(db, actor.tenant_id, schedule_id)


@router.get("/plays", response_model=Page[PlayOut])
async def plays(
    db: DB,
    actor: PlayReader,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
    state: Literal["authorized", "activated", "unknown", "refunded"] | None = None,
):
    filters = (PlaySession.status == state,) if state else ()
    return await ArcadeService().list_records(
        db, PlaySession, actor.tenant_id, page, limit, q=q, filters=filters
    )


@router.post("/plays/{play_id}/resolve", response_model=PlayOut)
async def resolve_play(play_id: UUID, payload: PlayResolution, db: DB, actor: PlayManager):
    return await ArcadeService().outcome(
        db, actor.tenant_id, play_id, payload.outcome, payload.reason, actor=actor
    )


@router.get("/shifts", response_model=Page[ShiftOut])
async def shifts(
    db: DB,
    actor: Cashier,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    # Cashiers see their own shifts. Reviewers use the separately authorized queue.
    return await ArcadeService().list_records(
        db,
        CashierShift,
        actor.tenant_id,
        page,
        limit,
        q=q,
        filters=(CashierShift.cashier_id == actor.id,),
    )


@router.get("/shifts/review", response_model=Page[ShiftOut])
async def shift_review_queue(
    db: DB,
    actor: ShiftManager,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(db, CashierShift, actor.tenant_id, page, limit, q=q)


@router.post("/shifts", response_model=ShiftOut, status_code=201)
async def open_shift(payload: ShiftOpen, db: DB, actor: Cashier):
    return await VenueService().open_shift(db, actor, payload)


@router.post("/shifts/{shift_id}/close", response_model=ShiftOut)
async def close_shift(shift_id: UUID, payload: ShiftClose, db: DB, actor: Cashier):
    return await VenueService().close_shift(db, actor, shift_id, payload)


@router.post("/shifts/{shift_id}/review", response_model=ShiftOut)
async def review_shift(shift_id: UUID, payload: Reason, db: DB, actor: ShiftManager):
    return await VenueService().review_shift(db, actor, shift_id, payload)


@router.post("/shifts/{shift_id}/movements", response_model=CashMovementOut, status_code=201)
async def cash_movement(shift_id: UUID, payload: CashMovementCreate, db: DB, actor: ShiftManager):
    return await VenueService().cash_movement(db, actor, shift_id, payload)


@router.post("/cashier/topups", response_model=ReceiptOut, status_code=201)
async def cash_topup(
    payload: CashTopup,
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.CASHIER_TOPUP))],
):
    return await VenueService().cash_topup(db, actor, payload)


@router.get("/receipts", response_model=Page[ReceiptOut])
async def receipts(
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.TRANSACTIONS_READ))],
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(db, Receipt, actor.tenant_id, page, limit, q=q)


@router.get("/topup-packages", response_model=Page[PackageOut])
async def packages(
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.ORG_READ))],
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(db, TopupPackage, actor.tenant_id, page, limit, q=q)


@router.post("/topup-packages", response_model=PackageOut, status_code=201)
async def create_package(payload: PackageCreate, db: DB, actor: PricingManager):
    return await VenueService().create_package(db, actor.tenant_id, payload)


@router.delete("/topup-packages/{package_id}", status_code=204)
async def disable_package(package_id: UUID, db: DB, actor: PricingManager):
    await VenueService().disable_package(db, actor.tenant_id, package_id)


@router.get("/customers/{customer_id}/workspace", response_model=CustomerWorkspace)
async def customer_workspace(
    customer_id: UUID,
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.CUSTOMERS_READ))],
):
    return await ArcadeService().customer_workspace(db, actor.tenant_id, customer_id)


@router.post("/customers/{customer_id}/portal-invitation", response_model=PortalInvitationOut)
async def portal_invitation(
    customer_id: UUID,
    payload: PortalInvite,
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.PORTAL_MANAGE))],
):
    return await CustomerPortalService().invite(db, actor.tenant_id, customer_id, payload.email)


@router.post("/families", response_model=FamilyOut, status_code=201)
async def create_family(payload: FamilyCreate, db: DB, actor: FamilyManager):
    return await ArcadeService().set_family(
        db, actor.tenant_id, payload.guardian_id, payload.child_id
    )


@router.get("/families", response_model=Page[FamilyOut])
async def list_families(
    db: DB,
    actor: FamilyManager,
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await ArcadeService().list_records(
        db, FamilyRelationship, actor.tenant_id, page, limit, q=q
    )


@router.put("/customers/{customer_id}/spending-limit", response_model=LimitOut)
async def set_limit(customer_id: UUID, payload: LimitUpdate, db: DB, actor: FamilyManager):
    return await ArcadeService().set_limit(db, actor.tenant_id, customer_id, payload)


@router.get("/alerts", response_model=Page[AlertOut])
async def alerts(
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.ALERTS_READ))],
    page: PageNumber = 1,
    limit: LimitNumber = 20,
    q: str | None = Query(None, max_length=200),
):
    return await OperationsService().visible_alerts(db, actor, page, limit, q)


@router.get("/staff/roles", response_model=list[RoleOut])
async def staff_roles(
    db: DB, actor: Annotated[User, Depends(require_admin_permission(P.USERS_MANAGE))]
):
    return await OperationsService().roles(db)


@router.post("/ledger/reconciliation/run", response_model=ReconciliationReportOut)
async def run_reconciliation(
    db: SnapshotDB, actor: Annotated[User, Depends(require_admin_permission(P.FINANCIAL_CONTROLS))]
):
    return await OperationsService().reconcile(db, actor.tenant_id)


@router.post("/ledger/resume", response_model=ReconciliationReportOut)
async def resume_financial_writes(
    payload: Reason,
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.FINANCIAL_CONTROLS))],
):
    return await OperationsService().resume_financial_writes(db, actor, payload.reason)


@router.post("/ledger/repair-wallet-cache", response_model=WalletBalanceOut)
async def repair_wallet_cache(
    payload: CacheRepair,
    db: DB,
    actor: Annotated[User, Depends(require_admin_permission(P.FINANCIAL_CONTROLS))],
):
    return await OperationsService().repair_cache(db, actor, payload)


@router.get("/reports/machines", response_model=list[MachineReportOut])
async def machine_report(
    db: SnapshotDB,
    actor: Annotated[User, Depends(require_admin_permission(P.REPORTS_READ))],
    start: date | None = None,
    end: date | None = None,
    currency: str | None = None,
    location_id: UUID | None = None,
):
    return await OverviewService().machine_reports(
        db, actor.tenant_id, start=start, end=end, currency=currency, location_id=location_id
    )
