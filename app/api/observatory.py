from fastapi import APIRouter
from app.models.schemas import (
    DomeStatus,
    DomeMoveRequest,
    DomeSyncStatus,
    ShutterStatus,
)

router = APIRouter(tags=["Observatory"])

# ---------------- Dome ----------------
@router.post("/dome/sync/on", response_model=DomeSyncStatus)
async def dome_sync_on():
    return DomeSyncStatus(dome_sync=True)


@router.post("/dome/sync/off", response_model=DomeSyncStatus)
async def dome_sync_off():
    return DomeSyncStatus(dome_sync=False)


@router.get("/dome/sync/status", response_model=DomeSyncStatus)
async def dome_sync_status():
    return DomeSyncStatus(dome_sync=True)


@router.post("/dome/move")
async def dome_move(request: DomeMoveRequest):
    return {"status": "moving", "target_az": request.az}


@router.get("/dome/status", response_model=DomeStatus)
async def dome_status():
    return DomeStatus(az=123.45, moving=False)


# ---------------- Shutter ----------------
@router.post("/shutter/open", response_model=ShutterStatus)
async def shutter_open():
    return ShutterStatus(shutter="open")


@router.post("/shutter/close", response_model=ShutterStatus)
async def shutter_close():
    return ShutterStatus(shutter="closed")


@router.get("/shutter/status", response_model=ShutterStatus)
async def shutter_status():
    return ShutterStatus(shutter="open")