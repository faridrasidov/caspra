# app/api/public/router.py

from fastapi import APIRouter

from app.api.public.endpoints import (
    auth,
    cards,
    customers,
    devices,
    events,
    metadata,
    org,
    products,
    reports,
    topup,
    transactions,
    webhooks,
)

public_router = APIRouter()
public_router.include_router(auth.router)
public_router.include_router(customers.router)
public_router.include_router(cards.router)
public_router.include_router(devices.router)
public_router.include_router(products.router)
public_router.include_router(transactions.router)
public_router.include_router(topup.router)
public_router.include_router(webhooks.router)
public_router.include_router(events.router)
public_router.include_router(org.router)
public_router.include_router(reports.router)
public_router.include_router(metadata.router)
