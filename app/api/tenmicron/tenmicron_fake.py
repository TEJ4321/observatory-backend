
"""
tenmicron_fake.py
=================

A fake version of the tenmicron.py driver for testing and development
without a real telescope mount. It simulates the state of the telescope,
including slewing, tracking, and position conversions using astropy.
"""
import time
import random
from typing import Tuple, Optional, Union, List

from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

class MountError(Exception):
    """Custom exception for 10Micron mount communication errors."""
    pass

class TenMicronMountFake:
    """
    A fake class that mimics the TenMicronMount for testing purposes.
    """

    STATUS_CODES = {
        "0": "Tracking",
        "1": "Stopped",
        "2": "Slewing to Park",
        "3": "Unparking",
        "4": "Slewing to Home",
        "5": "Parked",
        "6": "Slewing",
        "7": "Idle (Tracking Off)",
    }

    def __init__(self, host: str, port: int = 3492, timeout: float = 3.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._is_connected = False
        self._is_slewing = False
        self._is_tracking = False
        self._is_parked = True
        self._pier_side = "West"
        self._status = "Parked"

        # Fake location (e.g., UNSW Observatory)
        self._location = EarthLocation.from_geodetic(lat=-33.8559799094, lon=151.20666584, height=46)
        
        # Initial position (e.g., Polaris)
        self._current_ra_dec = SkyCoord("14h39m36.5s", "-60d50m02s", frame="icrs")
        self._target_ra_dec = None

        self._slew_start_time = 0
        self._slew_duration = 0
        self._slew_start_coords = None

    def connect(self):
        """Simulates connecting to the mount."""
        self._is_connected = True
        self._is_parked = False
        self._status = "Idle (Tracking Off)"
        print("Fake mount connected.")

    def close(self):
        """Simulates disconnecting from the mount."""
        self._is_connected = False
        print("Fake mount disconnected.")

    def _update_slew(self):
        """Update the slewing status and position."""
        if not self._is_slewing:
            return

        elapsed_time = time.time() - self._slew_start_time
        if elapsed_time >= self._slew_duration:
            self._is_slewing = False
            self._status = "Tracking" if self._is_tracking else "Idle (Tracking Off)"
            self._current_ra_dec = self._target_ra_dec
            self._slew_start_coords = None
        else:
            # Interpolate position during slew
            fraction = elapsed_time / self._slew_duration
            # This is a simplified linear interpolation. Real slews are more complex.
            # Astropy's SkyCoord doesn't directly support slerp, so we do it on the components.

            if self._target_ra_dec is None or self._slew_start_coords is None:
                return  # Should not happen if slewing, but good practice
            
            assert self._slew_start_coords is not None
            assert self._target_ra_dec is not None

            # Use separation to handle wrapping correctly for RA
            sep = self._slew_start_coords.separation(self._target_ra_dec)
            pos_angle = self._slew_start_coords.position_angle(self._target_ra_dec)
            interp_coord = self._slew_start_coords.directional_offset_by(pos_angle, sep * fraction)

            self._current_ra_dec = interp_coord


    def get_status(self) -> str:
        """Returns human-readable mount status."""
        self._update_slew()
        if self._is_slewing:
            return "Slewing"
        if self._is_parked:
            return "Parked"
        if self._is_tracking:
            return "Tracking"
        return "Idle (Tracking Off)"

    def get_mount_ra_dec(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """Return current RA and Dec."""
        self._update_slew()
        if as_float:
            return self._current_ra_dec.ra, self._current_ra_dec.dec # type: ignore
        return self._current_ra_dec.ra.to_string(), self._current_ra_dec.dec.to_string() # type: ignore

    def get_mount_alt_az(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """Return current Alt and Az."""
        self._update_slew()
        now = Time.now()
        alt_az_frame = AltAz(obstime=now, location=self._location)
        alt_az = self._current_ra_dec.transform_to(alt_az_frame) # type: ignore
        if as_float:
            return alt_az.alt, alt_az.az # type: ignore
        return alt_az.alt.to_string(unit=u.deg, sep=':'), alt_az.az.to_string(unit=u.deg, sep=':') # type: ignore

    def set_target_ra_dec(self, ra: Union[str, float], dec: Union[str, float]):
        """Set target RA/Dec coordinates for a slew."""
        try:
            if isinstance(ra, str):
                ra_unit = u.hourangle # type: ignore
            else: # float
                ra_unit = u.hour # type: ignore
            
            if isinstance(dec, str):
                dec_unit = u.deg # type: ignore
            else: # float
                dec_unit = u.deg # type: ignore

            self._target_ra_dec = SkyCoord(ra=ra, dec=dec, unit=(ra_unit, dec_unit), frame='icrs')
            return {'ra': '1', 'dec': '1'}
        except Exception:
            return {'ra': '0', 'dec': '0'}
        
    def set_target_alt_az(self, alt: Union[str, float], az: Union[str, float]):
        """Set target Alt/Az coordinates for a slew."""
        try:
            if isinstance(alt, str):
                alt_unit = u.deg # type: ignore
            else: # float
                alt_unit = u.deg # type: ignore

            if isinstance(az, str):
                az_unit = u.deg # type: ignore
            else: # float
                az_unit = u.deg # type: ignore

            self._target_ra_dec = SkyCoord(alt=alt, az=az, unit=(alt_unit, az_unit), frame='altaz', location=self._location)
            return {'alt': '1', 'az': '1'}
        except Exception:
            return {'alt': '0', 'az': '0'}


    def slew_to_target_equatorial(self, pier_side: Optional[str] = None) -> str:
        """Simulates slewing to the target."""
        if self._is_parked:
            return "Mount is Parked"
        if not self._target_ra_dec:
            return "No Object Set"
        
        self._update_slew() # update position before calculating separation
        
        if self._target_ra_dec is None:
            return "No Object Set"

        separation = self._current_ra_dec.separation(self._target_ra_dec) # type: ignore
        slew_rate = 10 * u.deg / u.s  # type: ignore # degrees per second
        self._slew_duration = (separation / slew_rate).to(u.s).value
        
        self._is_slewing = True
        self._slew_start_time = time.time()
        self._slew_start_coords = self._current_ra_dec
        self._status = "Slewing"
        
        if pier_side:
            self._pier_side = pier_side

        return "0" # Slew OK

    def park(self):
        """Simulates parking the mount."""
        self._is_parked = True
        self._is_tracking = False
        self._is_slewing = False
        self._status = "Parked"

    def unpark(self):
        """Simulates unparking the mount."""
        self._is_parked = False
        self._status = "Idle (Tracking Off)"

    def start_tracking(self):
        """Simulates starting tracking."""
        if not self._is_parked:
            self._is_tracking = True
            self._status = "Tracking"

    def stop_tracking(self):
        """Simulates stopping tracking."""
        self._is_tracking = False
        if not self._is_parked and not self._is_slewing:
            self._status = "Idle (Tracking Off)"

    def is_tracking(self) -> bool:
        """Returns tracking status."""
        return self._is_tracking

    def pier_side(self) -> str:
        """Return the current pier side."""
        return self._pier_side

    # --- Mocked methods returning plausible static or random data ---

    def get_status_code(self) -> str:
        """Return a plausible status code."""
        status = self.get_status()
        for code, text in self.STATUS_CODES.items():
            if text == status:
                return code
        return "98" # Unknown

    def target_trackable(self) -> bool:
        """Return whether the target is trackable."""
        return True

    def firmware_date(self) -> str:
        return "2023-10-26"

    def firmware_number(self) -> str:
        return "3.0.0 (fake)"

    def product_name(self) -> str:
        return "10Micron GM2000 HPS (Fake)"

    def firmware_time(self) -> str:
        return "10:00:00"

    def hardware_version(self) -> str:
        return "Fake HW v1.0"

    def get_lower_limit(self) -> str:
        return "+5"

    def get_upper_limit(self) -> str:
        return "+89"

    def get_target_ra_dec(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        if not self._target_ra_dec:
            return "", ""
        if as_float:
            return self._target_ra_dec.ra, self._target_ra_dec.dec # type: ignore
        return self._target_ra_dec.ra.to_string(unit=u.hour, sep=':'), self._target_ra_dec.dec.to_string(unit=u.deg, sep=':') # type: ignore

    def get_target_alt_az(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        if not self._target_ra_dec:
            return "", ""
        now = Time.now()
        alt_az_frame = AltAz(obstime=now, location=self._location)
        alt_az = self._target_ra_dec.transform_to(alt_az_frame)
        if as_float:
            return alt_az.alt.deg, alt_az.az.deg # type: ignore
        return alt_az.alt.to_string(unit=u.deg, sep=':'), alt_az.az.to_string(unit=u.deg, sep=':') # type: ignore

    def get_local_date_time(self) -> Tuple[str, str]:
        now = Time.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S") # type: ignore

    def get_utc_date_time(self) -> Tuple[str, str]:
        now = Time.now()
        return now.utc.strftime("%Y-%m-%d"), now.utc.strftime("%H:%M:%S") # type: ignore

    def get_utc_offset(self) -> str:
        return "+00:00:00.0"

    def get_sidereal_time(self) -> str:
        now = Time.now()
        sidereal_time = now.sidereal_time('mean', self._location.lon)
        return sidereal_time.to_string(unit=u.hour, sep=':', pad=True, precision=2) # type: ignore


    def get_julian_date(self, extra_precision: bool = False, leap_seconds: bool = False) -> str:
        return str(Time.now().jd)

    def get_connection_type(self) -> str:
        return "Cabled LAN"

    def get_ip_info(self, wireless: bool = False) -> Tuple[str, str, str, bool]:
        return ("127.0.0.1", "255.255.255.0", "127.0.0.1", True)

    def scan_wireless(self) -> bool:
        return False

    def wireless_access_points(self) -> List[Tuple[str, str]]:
        return []

    def home_status(self) -> str:
        return "1" # Home search found

    def seek_home(self):
        pass

    def stop_all_movement(self):
        self._is_slewing = False
        self._is_tracking = False

    def halt_movement(self, direction: Optional[str] = None):
        self._is_slewing = False

    def move_direction(self, direction: str):
        pass

    def nudge(self, direction: str, ms: int):
        pass

    def flip(self) -> str:
        if self._pier_side == "East":
            self._pier_side = "West"
        else:
            self._pier_side = "East"
        return "1"

    def get_element_temperature(self, element: int) -> Union[str, float]:
        return round(random.uniform(15.0, 40.0), 1)
        
    def send_command(self, cmd: str, *args, **kwargs) -> str:
        """A dummy send_command that can be used for debugging."""
        print(f"Fake mount received command: {cmd}")
        return "1" # Generic success


if __name__ == "__main__":
    mount = TenMicronMountFake("127.0.0.1")
    mount.connect()
    
    mount.get_status()
    ra, dec = mount.get_mount_ra_dec()
    print("RA:", ra, "DEC:", dec)
    alt, az = mount.get_mount_alt_az()
    print("ALT:", alt, "AZ:", az)
    mount.set_target_ra_dec("12:34:56.78", "+22:33:44.5")
    print(mount.slew_to_target_equatorial())
    print(mount.get_status())
    
    # Simulate some time passing for slew to complete
    time.sleep(5)
    print(mount.get_status())
    ra, dec = mount.get_mount_ra_dec()
    print("RA:", ra, "DEC:", dec)
    
    print("Pier Side:", mount.pier_side())
    mount.flip()
    print("Pier Side after flip:", mount.pier_side())

    mount.park()
    print("Status after park:", mount.get_status())
    mount.unpark()
    print("Status after unpark:", mount.get_status())

    print("Firmware Date:", mount.firmware_date())
    print("Product Name:", mount.product_name())
    print("Element 1 Temp:", mount.get_element_temperature(1))

    mount.close()
