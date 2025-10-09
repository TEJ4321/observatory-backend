from pydantic import BaseModel, Field
from typing import Optional

# ---------------- Telescope ----------------
class TelescopeStatus(BaseModel):
    """Current status of the mount."""
    status_code: str = Field(..., examples=["0"])
    status_text: str = Field(..., examples=["Tracking"])
    is_tracking: bool = Field(..., examples=[True])
    right_ascension: Optional[str | float] = Field(None, description="Righ Ascension in format '+DD:MM:SS', e.g.,12:34:56.78")
    declination: Optional[str | float] = Field(None, description="Declination in format '+DD:MM:SS', e.g., +22:33:44.5")
    altitude: Optional[str | float] = Field(None, description="Altitude in format '+DD:MM:SS', e.g., '+45:30:00'")
    azimuth: Optional[str | float] = Field(None, description="Azimuth in format 'DDD:MM:SS', e.g., '180:00:00'")

class TelescopeCoordinates(BaseModel):
    """Coordinates for RA/Dec or Alt/Az operations."""
    ra: Optional[float] = Field(None, description="Right Ascension in hours (decimal).")
    dec: Optional[float] = Field(None, description="Declination in degrees (decimal).")
    alt: Optional[float] = Field(None, description="Altitude in degrees.")
    az: Optional[float] = Field(None, description="Azimuth in degrees.")

class TelescopeSlewResult(BaseModel):
    """Response to a slew command."""
    result_code: str
    result_text: str

class TelescopeMessage(BaseModel):
    """Generic message response."""
    message: str

# ---------------- Dome ----------------
class DomeStatus(BaseModel):
    az: float = Field(..., description="Current dome azimuth in degrees")
    moving: bool = Field(..., description="Whether the dome is currently moving")


class DomeMoveRequest(BaseModel):
    az: float = Field(..., ge=0.0, le=360.0, description="Target dome azimuth in degrees (0–360)")


class DomeSyncStatus(BaseModel):
    dome_sync: bool = Field(..., description="True if dome is syncing with telescope")


# ---------------- Shutter ----------------
class ShutterStatus(BaseModel):
    shutter: str = Field(..., description="Shutter state: 'open' or 'closed'")
