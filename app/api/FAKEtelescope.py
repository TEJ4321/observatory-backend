from fastapi import APIRouter, HTTPException, Body
from app.models.schemas import (
    MountStatus,
    FirmwareInfo,
    MountLimits,
    TargetStatus,
    TimeInfo,
    NetworkStatus,
    HomeStatus,
    SetCoordinatesRequest,
    MessageResponse,
    TemperatureStatus
)
from app.api.tenmicron.tenmicron import MountError
import logging
import time as t
import random

router = APIRouter(prefix="/telescope", tags=["Telescope"])
logger = logging.getLogger("telescope")

# ----------------------------------------------------------------------
# GET ROUTES
# ----------------------------------------------------------------------

@router.get("/mount_status", response_model=MountStatus)
def get_mount_status():
    """Get all information about the mount's current status."""
    try:
        ra = 69 + (random.random() - 0.5) * 0.0001
        dec = 42 + (random.random() - 0.5) * 0.0001
        alt = 30 + (random.random() - 0.5) * 0.1
        az = 180 + (random.random() - 0.5) * 0.1
        date = t.strftime("%Y-%m-%d")
        time = t.strftime("%H:%M:%S")
        return MountStatus(
            status= "Idle",
            ra_str=str(ra), # type: ignore
            dec_str=str(dec), # type: ignore
            alt_str=str(alt), # type: ignore
            az_str=str(az), # type: ignore
            pier_side= "West",
            local_time=time,
            local_date=date,
            is_tracking=False,
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/firmware_info", response_model=FirmwareInfo)
def get_firmware_info():
    """Get firmware version and version information."""
    try:
        return FirmwareInfo(
            product_name="GM2000 HPS",
            firmware_number="2.13.2",
            firmware_date="2022-01-15",
            firmware_time="10:00:00",
            hardware_version="2.0",
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/limits", response_model=MountLimits)
def get_mount_limits():
    """Get the mount's configured limits."""
    try:
        return MountLimits(
            min_altitude="+1",
            max_altitude="+89",
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/target_status", response_model=TargetStatus)
def get_target_status():
    """Get all information about the target's current status."""
    try:
        ra = 50 + (random.random() - 0.5) * 0.0001
        dec = 90 + (random.random() - 0.5) * 0.0001
        alt = 45 + (random.random() - 0.5) * 0.1
        az = 270 + (random.random() - 0.5) * 0.1
        return TargetStatus(
            target_ra_str=str(ra),
            target_dec_str=str(dec),
            target_alt_str=str(alt),
            target_az_str=str(az),
            is_trackable=True,
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/time", response_model=TimeInfo)
def get_time():
    """Get the mount's current time and date."""
    try:
        local_date = t.strftime("%Y-%m-%d")
        local_time = t.strftime("%H:%M:%S")
        utc_date = t.strftime("%Y-%m-%d")
        utc_time = t.strftime("%H:%M:%S")
        return TimeInfo(
            local_time=local_time,
            local_date=local_date,
            utc_time=utc_time,
            utc_date=utc_date,
            utc_offset="+05:00:00",
            julian_date="JJJJJJJJ.JJJJJ",
            sidereal_time=utc_time,
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/network_status", response_model=NetworkStatus)
def get_network_status():
    """Get the mount's network status."""
    try:
        conn_type = "Cabled LAN"
        
        aps = []
        
        if conn_type == "Wireless LAN":
            ip, subnet, gateway, dhcp = ("192.168.1.10", "255.255.255.0", "192.168.1.1", True)
        elif conn_type == "Cabled LAN":
            ip, subnet, gateway, dhcp = ("192.168.1.10", "255.255.255.0", "192.168.1.1", True)
        else:
            raise ValueError(f"Unsupported connection type: {conn_type}")
        
        return NetworkStatus(
            ip_address=ip,
            subnet_mask=subnet,
            gateway=gateway,
            connection_type=conn_type,
            dhcp_enabled=dhcp,
            wireless_aps=aps,
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/home_status", response_model=HomeStatus)
def get_home_status():
    """Return the home status"""
    try:
        status_code = '0'
        status_map = {
            '0': "Home search failed",
            '1': "Home search found",
            '2': "Home search in progress"
        }
        return HomeStatus(
            is_homed=(status_code == '1'),
            status_description=status_map.get(status_code, "Unknown status")
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/temperatures", response_model=TemperatureStatus)
def get_all_temperatures():
    """Get the temperatures of various components of the mount."""

    return TemperatureStatus(
        motor_ra_az_driver=random.randint(200, 1000) / 10,
        motor_dec_alt_driver=random.randint(200, 1000) / 10,
        motor_ra_az=random.randint(200, 1000) / 10,
        motor_dec_alt=random.randint(200, 1000) / 10,
        electronics_box=random.randint(200, 1000) / 10,
        keypad_controller=random.randint(200, 1000) / 10,
        keypad_display=random.randint(200, 1000) / 10,
        keypad_pcb=random.randint(200, 1000) / 10
    )
    
# ----------------------------------------------------------------------
# POST ROUTES (Control)
# ----------------------------------------------------------------------

@router.post("/tracking/start", response_model=MessageResponse)
def start_tracking():
    """Start tracking."""
    return MessageResponse(message="Tracking enabled.")
    
@router.post("/tracking/stop", response_model=MessageResponse)
def stop_tracking():
    """Stop tracking."""
    return MessageResponse(message="Tracking disabled.")
        

@router.post("/target", response_model=MessageResponse)
def set_target(coords: SetCoordinatesRequest):
    """Set the target coordinates for a future slew."""
    return MessageResponse(message="Target set successfully.")
    
@router.post("/slew", response_model=MessageResponse)
def slew_to_target(pier_side: str | None = None):
    """Slew to the currently set target coordinates."""
    return MessageResponse(message="Slew command issued.")

@router.post("/flip", response_model=MessageResponse)
def flip_mount():
    """Flip the mount's pier side."""
    return MessageResponse(message="Flip command issued.")

@router.post("/park", response_model=MessageResponse)
def park_mount():
    """Park the mount."""
    return MessageResponse(message="Park command issued.")
    
@router.post("/unpark", response_model=MessageResponse)
def unpark_mount():
    """Unpark the mount."""
    return MessageResponse(message="Unpark command issued.")

@router.post("/home", response_model=MessageResponse)
def home_mount():
    """Start the mount's homing sequence."""
    return MessageResponse(message="Homing sequence initiated.")

@router.post("/nudge", response_model=MessageResponse)
def nudge_mount(direction: str, duration_ms: int):
    """Nudge the mount."""
    return MessageResponse(message="Nudge command issued.")

@router.post("/move", response_model=MessageResponse)
def move_mount(direction: str):
    """Start moving the mount in the specified direction."""
    return MessageResponse(message="Move command issued.")


@router.post("/halt", response_model=MessageResponse)
def halt_mount(direction: str | None = None):
    """Halt the mount's current movement in 1 or all directions."""
    return MessageResponse(message="Halt command issued.")

@router.post("/stop", response_model=MessageResponse)
def stop_mount():
    """Immediately stop ALL mount movement including tracking, slewing and homing."""
    return MessageResponse(message="STOP command issued.")

# ----------------------------------------------------------------------
# FOR DEBUGGING TELESCOPE/DRIVER CODE
# ----------------------------------------------------------------------

@router.post("/send_custom")
def send_custom_command(command: str = Body(..., embed=True)):
    """Send a custom command to the mount (WITHOUT THE TRAILING `#`)."""
    return MessageResponse(message="Command sent successfully.")