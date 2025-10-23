from fastapi import APIRouter, HTTPException
from contextlib import asynccontextmanager

from app.models.schemas import (
    DomeStatus,
    DomeMoveRequest,
    DomeSlaveRequest,
    DomeSyncStatus,
)
from .dome_fake import DomeFake, DomeError # Using fake dome
from .telescope import mount as telescope_mount # Import the mount instance


dome = DomeFake(mount=telescope_mount) # Pass mount instance to dome

@asynccontextmanager
async def lifespan(app: APIRouter):
    """Handle dome connection on startup and shutdown."""
    await dome.connect()
    yield
    await dome.close()

router = APIRouter(prefix="/dome", tags=["Dome"], lifespan=lifespan)

# ----------------------------------------------------------------------
# GET ROUTES
# ----------------------------------------------------------------------

@router.get("/status", response_model=DomeStatus)
async def dome_status():
    """Get the current azimuth and moving status of the dome."""
    try:
        az, moving = await dome.get_status()
        return DomeStatus(az=az, moving=moving)
    except DomeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/sync/status", response_model=DomeSyncStatus)
async def dome_sync_status():
    """Check if the dome is currently set to sync with the telescope."""
    try:
        is_syncing = await dome.get_sync_status()
        return DomeSyncStatus(dome_sync=is_syncing)
    except DomeError as e:
        raise HTTPException(status_code=503, detail=str(e))

# ----------------------------------------------------------------------
# POST ROUTES (Control)
# ----------------------------------------------------------------------

@router.post("/slew", response_model=DomeStatus)
async def dome_move(request: DomeMoveRequest):
    """Slew the dome to a specific azimuth."""
    try:
        await dome.move_to_azimuth(request.az)
        return await dome_status()
    except DomeError as e:
        raise HTTPException(status_code=409, detail=str(e)) # 409 Conflict if already moving

@router.post("/stop", response_model=DomeStatus)
async def dome_stop():
    """Stop any current dome movement."""
    try:
        await dome.stop_movement()
        return await dome_status()
    except DomeError as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/sync", response_model=DomeSyncStatus)
async def dome_set_slave(request: DomeSlaveRequest):
    """Enable or disable dome synchronization (slaving) with the telescope."""
    try:
        await dome.set_sync(request.slave)
        return DomeSyncStatus(dome_sync=await dome.get_sync_status())
    except DomeError as e:
        raise HTTPException(status_code=503, detail=str(e))