from fastapi import APIRouter
from app.models.schemas import (
    ShutterStatus
)

router = APIRouter(prefix="/shutter",tags=["Shutter"])

# ----------------------------------------------------------------------
# GET ROUTES
# ----------------------------------------------------------------------

@router.get("/status", response_model=ShutterStatus)
async def shutter_status():
    # Implement shutter status function
    return ShutterStatus(shutter="open")

# ----------------------------------------------------------------------
# POST ROUTES (Control)
# ----------------------------------------------------------------------

@router.post("/open", response_model=ShutterStatus)
async def shutter_open():
    # Implement shutter open function
    return ShutterStatus(shutter="open")

@router.post("/close", response_model=ShutterStatus)
async def shutter_close():
    # Implement shutter close function
    return ShutterStatus(shutter="closed")