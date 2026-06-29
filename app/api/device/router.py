# app/api/device/router.py

from fastapi import APIRouter

from app.api.device.endpoints import (
    auth,
    card,
    events,
    firmware,
    kiosk,
    offline,
    payment,
    settings,
    sync,
    system,
    transactions,
    ws,
)

device_router = APIRouter()
device_router.include_router(auth.router)
device_router.include_router(card.router)
device_router.include_router(payment.router)
device_router.include_router(transactions.router)
device_router.include_router(offline.router)
device_router.include_router(kiosk.router)
device_router.include_router(events.router)
device_router.include_router(settings.router)
device_router.include_router(firmware.router)
device_router.include_router(sync.router)
device_router.include_router(system.router)
device_router.include_router(ws.router)
