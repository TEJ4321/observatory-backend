from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    TelescopeStatus,
    TelescopeCoordinates,
    TelescopeSlewResult,
    TelescopeMessage,
)
from app.api.tenmicron import TenMicronMount, MountError

router = APIRouter(prefix="/telescope", tags=["Telescope"])

# Initialize mount (singleton-style for now)
mount = TenMicronMount("192.168.1.10", port=3492)

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("telescope")


@asynccontextmanager
async def lifespan(app):
    try:
        mount.connect()
    except Exception as e:
        logger.error(f"Failed to connect to 10Micron mount: {e}")
    yield
    try:
        mount.close()
    except Exception as e:
        logger.error(f"Error while disconnecting from 10Micron mount: {e}")

# To use this lifespan handler, you need to pass it to your FastAPI app:
# app = FastAPI(lifespan=lifespan)


# ----------------------------------------------------------------------
# Telescope Routes
# ----------------------------------------------------------------------

@router.get("/status", response_model=TelescopeStatus)
def get_mount_status():
    """Get current status, coordinates, and tracking state."""
    try:
        code = mount.get_status_code()
        status = mount.STATUS_CODES.get(code, f"Unknown ({code})")
        is_tracking = mount.is_tracking()
        ra, dec = mount.get_ra_dec()
        alt, az = mount.get_alt_az()

        return TelescopeStatus(
            status_code=code,
            status_text=status,
            is_tracking=is_tracking,
            right_ascension=ra,
            declination=dec,
            altitude=alt,
            azimuth=az,
        )
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slew/ra-dec", response_model=TelescopeSlewResult)
def slew_to_ra_dec(coords: TelescopeCoordinates):
    """Slew to target RA/Dec in decimal hours and degrees."""
    if coords.ra is None or coords.dec is None:
        raise HTTPException(status_code=400, detail="Both RA and Dec required.")
    try:
        mount.set_target_ra_dec(coords.ra, coords.dec)
        code = mount.send_command(":MS")
        text = mount.SLEW_RESULTS.get(code, f"Unknown ({code})")
        return TelescopeSlewResult(result_code=code, result_text=text)
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slew/alt-az", response_model=TelescopeSlewResult)
def slew_to_alt_az(coords: TelescopeCoordinates):
    """Slew to target Alt/Az in degrees."""
    if coords.alt is None or coords.az is None:
        raise HTTPException(status_code=400, detail="Both Alt and Az required.")
    try:
        mount.set_target_alt_az(coords.alt, coords.az)
        code = mount.send_command(":MA")
        text = mount.SLEW_RESULTS.get(code, f"Unknown ({code})")
        return TelescopeSlewResult(result_code=code, result_text=text)
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/park", response_model=TelescopeMessage)
def park_mount():
    """Park the telescope mount."""
    try:
        mount.park()
        return TelescopeMessage(message="Mount parking initiated.")
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unpark", response_model=TelescopeMessage)
def unpark_mount():
    """Unpark the telescope mount."""
    try:
        mount.unpark()
        return TelescopeMessage(message="Mount unparked.")
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop", response_model=TelescopeMessage)
def stop_mount():
    """Stop all motion immediately."""
    try:
        mount.stop_all()
        return TelescopeMessage(message="Mount motion stopped.")
    except MountError as e:
        raise HTTPException(status_code=500, detail=str(e))
