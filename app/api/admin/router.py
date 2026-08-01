# app/api/admin/router.py

from fastapi import APIRouter

from app.api.admin.endpoints import (
    apikeys,
    audit,
    auth,
    cards,
    customers,
    devices,
    kiosks,
    locations,
    notifications,
    offline,
    org,
    products,
    reconciliation,
    reports,
    settings,
    transactions,
    wallets,
    webhooks,
)

admin_router = APIRouter()
admin_router.include_router(auth.router)
admin_router.include_router(org.router)
admin_router.include_router(customers.router)
admin_router.include_router(cards.router)
admin_router.include_router(wallets.router)
admin_router.include_router(transactions.router)
admin_router.include_router(devices.router)
admin_router.include_router(kiosks.router)
admin_router.include_router(products.router)
admin_router.include_router(reconciliation.router)
admin_router.include_router(offline.router)
admin_router.include_router(locations.router)
admin_router.include_router(settings.router)
admin_router.include_router(reports.router)
admin_router.include_router(audit.router)
admin_router.include_router(webhooks.router)
admin_router.include_router(apikeys.router)
admin_router.include_router(notifications.router)
