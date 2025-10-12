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
    SlewRequest,
    TemperatureStatus
)
from app.api.tenmicron.tenmicron import TenMicronMount, MountError
import logging
import time
from contextlib import asynccontextmanager


router = APIRouter(prefix="/telescope", tags=["Telescope"])
mount = TenMicronMount("192.168.1.10", port=3492, timeout=10)

logger = logging.getLogger("telescope")

@asynccontextmanager
async def lifespan(app):
    try:
        mount.connect()
    except Exception as e:
        logger.error(f"Failed to connect to mount: {e}")
    yield
    try:
        mount.close()
    except Exception as e:
        logger.error(f"Error while disconnecting from mount: {e}")

# ----------------------------------------------------------------------
# GET ROUTES
# ----------------------------------------------------------------------

@router.get("/mount_status", response_model=MountStatus)
def get_mount_status():
    """Get all information about the mount's current status."""
    try:
        ra, dec = mount.get_mount_ra_dec()
        alt, az = mount.get_mount_alt_az()
        date, time = mount.get_local_date_time()
        return MountStatus(
            status=mount.get_status(),
            ra_str=ra, # type: ignore
            dec_str=dec, # type: ignore
            alt_str=alt, # type: ignore
            az_str=az, # type: ignore
            pier_side=mount.pier_side(),
            local_time=time,
            local_date=date,
            is_tracking=mount.is_tracking(),
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/firmware_info", response_model=FirmwareInfo)
def get_firmware_info():
    """Get firmware version and version information."""
    try:
        return FirmwareInfo(
            product_name=mount.product_name(),
            firmware_number=mount.firmware_number(),
            firmware_date=mount.firmware_date(),
            firmware_time=mount.firmware_time(),
            hardware_version=mount.hardware_version(),
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/limits", response_model=MountLimits)
def get_mount_limits():
    """Get the mount's configured limits."""
    try:
        return MountLimits(
            min_altitude=mount.get_lower_limit(),
            max_altitude=mount.get_upper_limit(),
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/target_status", response_model=TargetStatus)
def get_target_status():
    """Get all information about the target's current status."""
    try:
        ra, dec = mount.get_target_ra_dec()
        alt, az = mount.get_target_alt_az()
        return TargetStatus(
            target_ra_str=ra,
            target_dec_str=dec,
            target_alt_str=alt,
            target_az_str=az,
            is_trackable=mount.target_trackable(),
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/time", response_model=TimeInfo)
def get_time():
    """Get the mount's current time and date."""
    try:
        local_date, local_time = mount.get_local_date_time()
        utc_date, utc_time = mount.get_utc_date_time()
        return TimeInfo(
            local_time=local_time,
            local_date=local_date,
            utc_time=utc_time,
            utc_date=utc_date,
            utc_offset=mount.get_utc_offset(),
            julian_date=mount.get_julian_date(extra_precision=True),
            sidereal_time=mount.get_sidereal_time(),
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


@router.get("/network_status", response_model=NetworkStatus)
def get_network_status():
    """Get the mount's network status."""
    try:
        conn_type = mount.get_connection_type()
        
        aps = []
        if mount.scan_wireless():
            time.sleep(1)
            try:
                aps = mount.wireless_access_points()
            except MountError as e:
                if "Wireless scan is still underway" in str(e):
                    pass
                else:
                    raise e
        
        if conn_type == "Wireless LAN":
            ip, subnet, gateway, dhcp = mount.get_ip_info(wireless=True)
        elif conn_type == "Cabled LAN":
            ip, subnet, gateway, dhcp = mount.get_ip_info(wireless=False)
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
        status_code = mount.home_status()
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
    
    elements_dict = {
        1: "Right Ascension/Azimuth motor driver",
        2: "Declination/Altitude motor driver",
        7: "Right Ascension/Azimuth motor",
        8: "Declination/Altitude motor",
        9: "Electronics box temperature sensor",
        11: "Keypad (v2) display sensor",
        12: "Keypad (v2) PCB sensor",
        13: "Keypad (v2) controller sensor"
    }
    
    temperatures = {}
    
    try:
        for element, name in elements_dict.items():
            temp = mount.get_element_temperature(element)
            if temp == "Unavailable":
                continue
            temperatures[name] = float(temp)
        return TemperatureStatus(
            motor_ra_az_driver=temperatures.get("Right Ascension/Azimuth motor driver", None),
            motor_dec_alt_driver=temperatures.get("Declination/Altitude motor driver", None),
            motor_ra_az=temperatures.get("Right Ascension/Azimuth motor", None),
            motor_dec_alt=temperatures.get("Declination/Altitude motor", None),
            electronics_box=temperatures.get("Electronics box temperature sensor", None),
            keypad_controller=temperatures.get("Keypad (v2) controller sensor", None),
            keypad_display=temperatures.get("Keypad (v2) display sensor", None),
            keypad_pcb=temperatures.get("Keypad (v2) PCB sensor", None)
        )
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")


# ----------------------------------------------------------------------
# POST ROUTES (Control)
# ----------------------------------------------------------------------

@router.post("/target", response_model=MessageResponse)
def set_target(coords: SetCoordinatesRequest):
    """Set the target coordinates for a future slew."""
    try:
        if coords.ra is not None and coords.dec is not None:
            result = mount.set_target_ra_dec(coords.ra, coords.dec)
            if result['ra'] == '0' or result['dec'] == '0':
                raise HTTPException(status_code=400, detail=f"Invalid RA/Dec coordinates provided. RA valid: {result['ra']}, Dec valid: {result['dec']}")
            return MessageResponse(message="Equatorial target set successfully.")
        elif coords.alt is not None and coords.az is not None:
            result = mount.set_target_alt_az(coords.alt, coords.az)
            if result['alt'] == '0' or result['az'] == '0':
                raise HTTPException(status_code=400, detail=f"Invalid Alt/Az coordinates provided. Alt valid: {result['alt']}, Az valid: {result['az']}")
            return MessageResponse(message="Altitude/Azimuth target set successfully.")
        else:
            raise HTTPException(status_code=400, detail="Request must include either (RA, Dec) or (Alt, Az).")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")

@router.post("/slew", response_model=MessageResponse)
def slew_to_target(slew_request: SlewRequest):
    """Slew to the currently set target coordinates."""
    try:
        # The driver's slew command returns a complex string. We simplify it here.
        # A more advanced implementation could parse the slew result code.
        mount.slew_to_target_equatorial(pier_side=slew_request.pier_side)
        return MessageResponse(message="Slew command issued.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/park", response_model=MessageResponse)
def park_mount():
    """Park the mount."""
    try:
        mount.park()
        return MessageResponse(message="Park command issued.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")

@router.post("/unpark", response_model=MessageResponse)
def unpark_mount():
    """Unpark the mount."""
    try:
        mount.unpark()
        return MessageResponse(message="Unpark command issued.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")

@router.post("/home", response_model=MessageResponse)
def home_mount():
    """Start the mount's homing sequence."""
    try:
        mount.seek_home()
        return MessageResponse(message="Homing sequence initiated.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")

@router.post("/stop", response_model=MessageResponse)
def stop_mount():
    """Immediately stop all mount movement."""
    try:
        mount.stop_all_movement()
        return MessageResponse(message="STOP command issued.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")



# ----------------------------------------------------------------------
# FOR DEBUGGING TELESCOPE/DRIVER CODE
# ----------------------------------------------------------------------

@router.post("/send_custom")
def send_custom_command(command: str = Body(..., embed=True)):
    """Send a custom command to the mount (WITHOUT THE TRAILING `#`)."""
    try:
        mount.send_command(command)
        return MessageResponse(message="Command sent successfully.")
    except MountError as e:
        raise HTTPException(status_code=503, detail=f"Mount communication error: {e}")