from pydantic import BaseModel, Field
from typing import Optional, List, Tuple

# ---------------- Telescope ----------------

class MountStatus(BaseModel):
    """Comprehensive status of the mount."""
    status: str = Field(..., description="Human-readable mount status (e.g., 'Tracking', 'Parked').", examples=["Tracking"])
    ra_str: str = Field(..., description="Current Right Ascension in HH:MM:SS.SS format.", examples=["12:34:56.78"])
    dec_str: str = Field(..., description="Current Declination in sDD:MM:SS.S format.", examples=["+22:33:44.5"])
    alt_str: str = Field(..., description="Current Altitude in sDD:MM:SS.S format.", examples=["+45:30:00.0"])
    az_str: str = Field(..., description="Current Azimuth in DDD:MM:SS.S format.", examples=["180:00:00.0"])
    pier_side: str = Field(..., description="Current pier side ('East' or 'West').", examples=["East"])
    local_time: str = Field(..., description="Mount's local time in HH:MM:SS.SS format.", examples=["22:10:30.55"])
    local_date: str = Field(..., description="Mount's local date in YYYY-MM-DD format.", examples=["2023-10-27"])
    is_tracking: bool = Field(..., description="True if the mount is currently tracking.", examples=[True])

class FirmwareInfo(BaseModel):
    """Mount firmware and hardware version information."""
    product_name: str
    firmware_number: str
    firmware_date: str
    firmware_time: str
    hardware_version: str
    class Config:
        json_schema_extra = {
            "example": {
                "product_name": "GM2000 HPS",
                "firmware_number": "2.13.2",
                "firmware_date": "2022-01-15",
                "firmware_time": "10:00:00",
                "hardware_version": "2.0"
            }
        }

class MountLimits(BaseModel):
    """Mount's configured altitude limits."""
    min_altitude: str = Field(..., description="Lowest altitude the mount will slew to.", examples=["+10"])
    max_altitude: str = Field(..., description="Highest altitude the mount will slew to.", examples=["+85"])

class TargetStatus(BaseModel):
    """Information about the currently set target."""
    target_ra_str: Optional[str | float] = Field(None, description="Target Right Ascension in HH:MM:SS.SS format.", examples=["18:36:56.33"])
    target_dec_str: Optional[str | float] = Field(None, description="Target Declination in sDD:MM:SS.S format.", examples=["-38:47:01.2"])
    target_alt_str: Optional[str | float] = Field(None, description="Target Altitude in sDD:MM:SS.S format.", examples=["+55:12:34.5"])
    target_az_str: Optional[str | float] = Field(None, description="Target Azimuth in DDD:MM:SS.S format.", examples=["210:45:10.0"])
    is_trackable: bool = Field(..., description="True if the target is in a trackable position.", examples=[True])

class TimeInfo(BaseModel):
    """Various time and date information from the mount."""
    local_time: str = Field(..., examples=["22:10:30.55"])
    local_date: str = Field(..., examples=["2023-10-27"])
    utc_time: str = Field(..., examples=["02:10:30.55"])
    utc_date: str = Field(..., examples=["2023-10-28"])
    utc_offset: str = Field(..., examples=["-04:00:00.0"])
    julian_date: str = Field(..., examples=["2460244.590631"])
    sidereal_time: str = Field(..., examples=["05:45:12.34"])

class NetworkStatus(BaseModel):
    """Mount's network configuration."""
    ip_address: str = Field(..., examples=["192.168.1.10"])
    subnet_mask: str = Field(..., examples=["255.255.255.0"])
    gateway: str = Field(..., examples=["192.168.1.1"])
    connection_type: str = Field(..., description="'Wired' or 'Wireless'", examples=["Cabled LAN"])
    dhcp_enabled: bool = Field(..., examples=[False])
    wireless_aps: Optional[List[Tuple[str, str]]] = Field(None, description="List of (SSID, Security Type) for available Wi-Fi networks.", examples=[[("MyObservatoryWiFi", "WPA2")]])

class HomeStatus(BaseModel):
    """Mount's homing status."""
    is_homed: bool = Field(..., examples=[True])
    status_description: str = Field(..., examples=["Home search found"])

class TemperatureStatus(BaseModel):
    """Temperatures of various mount components."""
    motor_ra_az_driver: Optional[float] = Field(None, description="Temperature of the RA/Az motor driver in Celsius.")
    motor_dec_alt_driver: Optional[float] = Field(None, description="Temperature of the Dec/Alt motor driver in Celsius.")
    motor_ra_az: Optional[float] = Field(None, description="Temperature of the RA/Az motor in Celsius.")
    motor_dec_alt: Optional[float] = Field(None, description="Temperature of the Dec/Alt motor in Celsius.")
    electronics_box: Optional[float] = Field(None, description="Temperature of the electronics box sensor in Celsius.")
    keypad_display: Optional[float] = Field(None, description="Temperature of the Keypad (v2) display sensor in Celsius.")
    keypad_pcb: Optional[float] = Field(None, description="Temperature of the Keypad (v2) PCB sensor in Celsius.")
    keypad_controller: Optional[float] = Field(None, description="Temperature of the Keypad (v2) controller sensor in Celsius.")
    class Config:
        json_schema_extra = {
            "example": {
                "motor_ra_az_driver": 25.5,
                "motor_dec_alt_driver": 26.1,
                "motor_ra_az": 30.2,
                "motor_dec_alt": 31.0,
                "electronics_box": 28.7,
                "keypad_display": 24.0,
                "keypad_pcb": 27.3,
                "keypad_controller": 29.8
            }
        }

class SetCoordinatesRequest(BaseModel):
    """Request to set target coordinates. Can be RA/Dec or Alt/Az."""
    ra: Optional[str | float] = Field(None, description="Right Ascension in 'HH:MM:SS.ss' or decimal hours.", examples=["18:36:56.33"])
    dec: Optional[str | float] = Field(None, description="Declination in 'sDD:MM:SS.s' or decimal degrees.", examples=["-38:47:01.2"])
    alt: Optional[str | float] = Field(None, description="Altitude in 'sDD:MM:SS.s' or decimal degrees.", examples=["+45:00:00"])
    az: Optional[str | float] = Field(None, description="Azimuth in 'DDD:MM:SS.s' or decimal degrees.", examples=["180:00:00"])

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str = Field(..., examples=["Command issued."])

class FlipResponse(BaseModel):
    """Response to a flip mount request."""
    sucess: bool = Field(..., description="True if the flip was successful.", examples=[True])
    


# ---------------- Dome ----------------
class DomeStatus(BaseModel):
    az: float = Field(..., description="Current dome azimuth in degrees", examples=[123.45])
    moving: bool = Field(..., description="Whether the dome is currently moving", examples=[False])


class DomeMoveRequest(BaseModel):
    az: float = Field(..., ge=0.0, le=360.0, description="Target dome azimuth in degrees (0-360)", examples=[180.0])


class DomeSyncStatus(BaseModel):
    dome_sync: bool = Field(..., description="True if dome is syncing with telescope", examples=[True])








# ---------------- Shutter ----------------
class ShutterStatus(BaseModel):
    shutter: str = Field(..., description="Shutter state: 'open' or 'closed'", examples=["open"])




# ---------------- System -----------------
class SystemNetworkStatus(BaseModel):
    name: str
    family: Optional[str]
    ip_address: Optional[str]
    mac_address: Optional[str]
    subnet_mask: Optional[str]
    broadcast: Optional[str]
    
class DiskData(BaseModel):
    device: str
    mountpoint: str
    fstype: str
    total: Optional[str]
    used: Optional[str]
    free: Optional[str]
    percent: Optional[float]

class SystemStatus(BaseModel):
    system: str
    node_name: str
    version: str
    machine: str
    processor: Optional[str]
    boot_time: str
    uptime: str
    cpu_physical_cores: Optional[int]
    cpu_logical_cores: Optional[int]
    cpu_max_frequency: float
    cpu_current_frequency: float
    cpu_usage: float
    memory_total: Optional[str]
    memory_available: Optional[str]
    memory_used: Optional[str]
    memory_usage: float
    disks: List[DiskData]
    network_interfaces: List[SystemNetworkStatus]
    network_sent: Optional[str]
    network_received: Optional[str]
    cpu_temperature: Optional[dict[str, list]]
    
