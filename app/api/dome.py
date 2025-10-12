from fastapi import APIRouter
from app.models.schemas import (
    DomeStatus,
    DomeMoveRequest,
    DomeSyncStatus,
)

router = APIRouter(prefix="/dome",tags=["Dome"])

# ----------------------------------------------------------------------
# GET ROUTES
# ----------------------------------------------------------------------

@router.get("/status", response_model=DomeStatus)
async def dome_status():
    # Implement dome status and position function
    return DomeStatus(az=123.45, moving=False)

@router.get("/sync/status", response_model=DomeSyncStatus)
async def dome_sync_status():
    # Implement dome sync status function
    return DomeSyncStatus(dome_sync=True)

# ----------------------------------------------------------------------
# POST ROUTES (Control)
# ----------------------------------------------------------------------

@router.post("/move")
async def dome_move(request: DomeMoveRequest):
    # Implement dome move function
    return {"status": "moving", "target_az": request.az}

@router.post("/sync/on", response_model=DomeSyncStatus)
async def dome_sync_on():
    # Implement dome sync function
    return DomeSyncStatus(dome_sync=True)

@router.post("/sync/off", response_model=DomeSyncStatus)
async def dome_sync_off():
    # Implement dome sync function
    return DomeSyncStatus(dome_sync=False)