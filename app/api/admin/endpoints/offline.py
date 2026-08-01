from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.admin_permissions import AdminPermission
from app.models.identity.user import User
from app.schemas.device_txn import (
    OfflinePolicyOut,
    OfflinePolicyUpdate,
    OfflineReviewDecision,
    OfflineReviewItemOut,
)
from app.services.device_offline import DeviceOfflineService

router = APIRouter(prefix="/offline", tags=["admin-offline"])


@router.get("/policy", response_model=OfflinePolicyOut | None)
async def get_offline_policy(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.DEVICES_READ))
    ],
) -> OfflinePolicyOut | None:
    policy = await DeviceOfflineService().get_policy(db, current_admin.tenant_id)
    return OfflinePolicyOut.model_validate(policy) if policy is not None else None


@router.put("/policy", response_model=OfflinePolicyOut)
async def update_offline_policy(
    payload: OfflinePolicyUpdate,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.DEVICES_MANAGE))
    ],
) -> OfflinePolicyOut:
    policy = await DeviceOfflineService().update_policy(db, current_admin.tenant_id, payload)
    return OfflinePolicyOut.model_validate(policy)


@router.get("/review", response_model=list[OfflineReviewItemOut])
async def list_offline_review(
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.TRANSACTIONS_READ))
    ],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[OfflineReviewItemOut]:
    records = await DeviceOfflineService().list_review(db, current_admin.tenant_id, status_filter)
    return [OfflineReviewItemOut.model_validate(record) for record in records]


@router.post("/review/{offline_transaction_id}", response_model=OfflineReviewItemOut)
async def decide_offline_review(
    offline_transaction_id: UUID,
    payload: OfflineReviewDecision,
    db: Annotated[AsyncSession, Depends(deps.get_db)],
    current_admin: Annotated[
        User, Depends(deps.require_admin_permission(AdminPermission.WALLETS_ADJUST))
    ],
) -> OfflineReviewItemOut:
    record = await DeviceOfflineService().review(
        db,
        current_admin.tenant_id,
        offline_transaction_id,
        current_admin,
        payload,
    )
    return OfflineReviewItemOut.model_validate(record)
