"""
tenmicron.py
============

Python interface for 10Micron GM2000 and compatible telescope mounts.
Should also work with GM1000, GM3000, GM4000, HPS, QCI, AZ2000 and others.
Implements the LX200-compatible Mount Control Protocol (v2.13.2),
including 10Micron-specific extensions.

Features:
---------
- Full ultra-precision mode (U2) enabled on connect.
- High-level wrappers for RA/Dec and Alt/Az movement.
- Human-readable mount statuses and slew results.
- Safe decoding of non-ASCII LX200 degree symbols (0xDF).
- Common control functions: slew, park, unpark, home, stop.
- Time/date and firmware query/set functions.
- Network and safety limit utilities.

Protocol Reference:
-------------------
All commands implemented are defined in the official
10Micron Mount Command Protocol document (rev. 2.13.2).
Located at:
https://manualzz.com/doc/30467825/10micron-gm1000-hps--gm2000-qci--hps--gm3000-hps--gm4000-...?p=2

Notes:
-------------------
- The commands were scraped from the manual partially using Generative AI, and not all have been tested.

Author: Tejas
License: MIT
"""

import socket
import re
from typing import Tuple, Optional, Union

class MountError(Exception):
    """Custom exception for 10Micron mount communication errors."""
    pass

class TenMicronMount:
    """
    A class to control a 10Micron GM series mount via TCP/IP.

    Example:
    --------
    >>> mount = TenMicronMount("192.168.1.10")
    >>> mount.connect()
    >>> print(mount.get_status())
    >>> ra, dec = mount.get_ra_dec()
    >>> print("RA:", ra, "DEC:", dec)
    >>> mount.set_target_ra_dec("12:34:56.78", "+22:33:44.5")
    >>> print(mount.slew_to_target_equatorial())
    >>> mount.close()
    """

    # ------------------------------------------------------------------
    # Human-readable mappings from protocol return codes
    # ------------------------------------------------------------------

    STATUS_CODES = {
        "0": "Tracking",
        "1": "Stopped",
        "2": "Slewing to Park",
        "3": "Unparking",
        "4": "Slewing to Home",
        "5": "Parked",
        "6": "Slewing",
        "7": "Idle (Tracking Off)",
        "8": "Motors Inhibited (Low Temp)",
        "9": "Tracking Outside Limits",
        "10": "Satellite Tracking",
        "11": "Awaiting User Confirmation",
        "98": "Unknown",
        "99": "Error",
    }

    SLEW_RESULTS = {
        "0": "Slew OK",
        "1": "Below Horizon",
        "2": "Limit Error",
        "3": "Object is Below Horizon",
        "4": "Object is Beyond Limits",
        "5": "Mount is Parked",
        "6": "Mount is Not Aligned",
        "7": "No Object Set",
        "8": "Tracking Disabled",
        "9": "Mount Busy",
        "10": "Refraction Disabled",
        "99": "Unknown Slew Error",
    }

    def __init__(self, host: str, port: int = 3492, timeout: float = 3.0):
        """
        Initialize the TenMicronMount instance.

        Parameters
        ----------
        host : str
            IP address or hostname of the mount on the local network.
        port : int, optional
            TCP port used for control (default is 3492, but 3490 will likely work too).
        timeout : float, optional
            Socket timeout in seconds (default is 3.0).
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None


    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self):
        """
        Establish a TCP/IP connection to the 10Micron mount and enable
        ultra-precision mode (U2).

        Raises
        ------
        MountError
            If the connection fails.
        """
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)
        # Enable ultra-precision mode
        self.send_command(":U2", expect_response=False)

    def close(self):
        """Close the TCP connection to the mount."""
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    # ------------------------------------------------------------------
    # Core communication
    # ------------------------------------------------------------------
    def send_command(self, cmd: str, expect_response: bool = True, timeout: Optional[float] = None) -> str:
        """
        Send a raw command to the mount and read the response.

        Parameters
        ----------
        cmd : str
            The mount command string (without the trailing '#').
        expect_response : bool, optional
            If False, the function returns immediately after sending. (Default is True)
        timeout : float, optional
            Override socket timeout for this command.

        Returns
        -------
        str
            Response string from the mount (without trailing '#').

        Raises
        ------
        MountError
            If the connection fails or times out.
        """
        if not self.sock:
            raise RuntimeError("Not connected to mount. Make sure IP and port are correct.")
        if timeout is None:
            timeout = self.timeout
        self.sock.settimeout(timeout)
        


        try:
            self.sock.sendall(f"{cmd}#".encode("ascii"))
            if not expect_response:
                return ""
            data = b""
            while not data.endswith(b"#"):
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            raise MountError(f"Timeout waiting for response to {cmd}")
        except Exception as e:
            raise MountError(f"Communication error: {e}")



        # 0xDF often appears as ß in latin-1; convert to degree sign for readability
        decoded = data.decode("latin-1").replace("ß", "°").strip("#")

        # Alternative 1:
        # decoded = data.decode("utf-8", errors="ignore").strip("#")

        # Alternative 2: # Replace the LX200 degree marker (0xDF)
        # decoded = data.decode("latin-1").rstrip("#")
        # decoded = decoded.replace("\xdf", "°").replace("ß", "°")

        return decoded
    

    # ------------------------------------------------------------------
    # Formatters and parsers
    # ------------------------------------------------------------------
    @staticmethod
    def _hours_to_hms(hours: float) -> str:
        """Convert decimal hours → HH:MM:SS.SS"""
        h = int(hours)
        m = int((hours - h) * 60)
        s = (hours - h - m/60) * 3600
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _degrees_to_dms(deg: float, signed=True) -> str:
        """Convert decimal degrees → ±DD:MM:SS.S"""
        sign = "-" if deg < 0 else "+"
        d = abs(int(deg))
        m = int((abs(deg) - d) * 60)
        s = (abs(deg) - d - m/60) * 3600
        if signed:
            return f"{sign}{d:02d}:{m:02d}:{s:05.2f}"
        return f"{d:03d}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _hms_to_hours(ra_str: str) -> float:
        """Convert HH:MM:SS.SS → decimal hours"""
        h, m, s = map(float, re.split(r"[:]", ra_str))
        return h + m/60 + s/3600

    @staticmethod
    def _dms_to_degrees(dec_str: str) -> float:
        """Convert ±DD:MM:SS.S → decimal degrees"""
        sign = -1 if dec_str.strip().startswith("-") else 1
        d, m, s = map(float, re.split(r"[:]", dec_str.strip("+-")))
        return sign * (abs(d) + m/60 + s/3600)

    # ------------------------------------------------------------------
    # Status and tracking
    # ------------------------------------------------------------------
    def get_status_code(self) -> str:
        """Return the raw status code (`:Gstat#`)."""
        return self.send_command(":Gstat")

    def get_status(self) -> str:
        """Returns human-readable mount status."""
        code = self.get_status_code()
        return self.STATUS_CODES.get(code, f"Unknown ({code})")

    def is_tracking(self) -> bool:
        """Returns True if mount is currently tracking."""
        return self.send_command(":GTRK") == "1"

    def is_ready(self) -> bool:
        """Check if mount can accept slews (status codes 0 or 7)."""
        # ready = tracking (0) or idle (7). Use get_status_code to be exact.
        code = self.get_status_code()
        return code in ("0", "7")  # Tracking or idle

    # ------------------------------------------------------------------
    # RA/Dec coordinate control
    # ------------------------------------------------------------------

    def get_ra(self) -> str:
        """Return current Right Ascension (`:GR#`)."""
        return self.send_command(":GR")

    def get_dec(self) -> str:
        """Return current Declination (`:GD#`)."""
        return self.send_command(":GD")
    
    def get_ra_dec(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return current RA and Dec.

        Parameters
        ----------
        as_float : bool
            If True, return (hours, degrees) as floats.
        """
        ra = self.get_ra()
        dec = self.get_dec()
        if as_float:
            return self._hms_to_hours(ra), self._dms_to_degrees(dec)
        return ra, dec

    def set_target_ra_dec(self, ra: Union[str, float], dec: Union[str, float]) -> dict:
        """
        Set target RA/Dec for a for a future slew.

        Parameters
        ----------
        ra : str or float
            Right ascension in 'HH:MM:SS' or decimal hours.
        dec : str or float
            Declination in '+DD:MM:SS' or decimal degrees.
        """
        if isinstance(ra, (int, float)):
            ra = self._hours_to_hms(ra)
        if isinstance(dec, (int, float)):
            dec = self._degrees_to_dms(dec, signed=True)
        return {
            "ra": self.send_command(f":Sr{ra}"),
            "dec": self.send_command(f":Sd{dec}")
        }

    def slew_to_target_equatorial(self) -> str:
        """
        Slew to the previously set RA/Dec target (`:MS#`).

        Returns
        -------
        str
            Human-readable slew result.
        """
        code = self.send_command(":MS")
        return self.SLEW_RESULTS.get(code, f"Unknown ({code})")


    # ------------------------------------------------------------------
    # Alt/Az coordinate control
    # ------------------------------------------------------------------
    def get_alt(self) -> str:
        """Return current altitude (`:GA#`)."""
        return self.send_command(":GA")

    def get_az(self) -> str:
        """Return current azimuth (`:GZ#`)."""
        return self.send_command(":GZ")

    def get_alt_az(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return current Alt and Az.

        Parameters
        ----------
        as_float : bool
            If True, return (degrees, degrees) as floats.
        """
        alt = self.get_alt()
        az = self.get_az()
        if as_float:
            return self._dms_to_degrees(alt), self._dms_to_degrees(az)
        return alt, az


    def set_target_alt_az(self, alt: Union[str, float], az: Union[str, float]) -> dict:
        """
        Set target Alt/Az coordinates for a slew.

        Parameters
        ----------
        alt : str or float
            Altitude in '+DD:MM:SS' or decimal degrees.
        az : str or float
            Azimuth in 'DDD:MM:SS' or decimal degrees.
        """
        if isinstance(alt, (int, float)):
            alt = self._degrees_to_dms(alt, signed=True)
        if isinstance(az, (int, float)):
            az = self._degrees_to_dms(az, signed=False)
        return {
            "alt": self.send_command(f":Sa{alt}"),
            "az": self.send_command(f":Sz{az}")
        }

    def slew_to_target_altaz(self) -> str:
        """
        Slew to the previously set Alt/Az target (`:MA#`).

        Returns
        -------
        str
            Human-readable slew result.
        """
        code = self.send_command(":MA")
        return self.SLEW_RESULTS.get(code, f"Unknown ({code})")


    # ------------------------------------------------------------------
    # Movement and motion control
    # ------------------------------------------------------------------
    def stop_all(self):
        """Immediately stop all movement (`:STOP#`)."""
        self.send_command(":STOP", expect_response=False)

    def halt(self):
        """Abort current slew (`:Q#`)."""
        self.send_command(":Q", expect_response=False)

    def move_direction(self, direction: str):
        """
        Start manual movement in a cardinal direction.

        Parameters
        ----------
        direction : {'N', 'S', 'E', 'W'}
            Direction to move.
        """
        direction = direction.upper()
        if direction not in {"N", "S", "E", "W"}:
            raise ValueError("Direction must be one of N, S, E, W")
        self.send_command(f":M{direction.lower()}", expect_response=False)

    def nudge(self, direction: str, ms: int):
        """
        Send a short guiding pulse in a direction.

        Parameters
        ----------
        direction : {'N', 'S', 'E', 'W'}
            Direction to pulse.
        ms : int
            Duration in milliseconds.
        """
        direction = direction.upper()
        if direction not in {"N", "S", "E", "W"}:
            raise ValueError("Direction must be one of N, S, E, W")
        self.send_command(f":M{direction.lower()}{ms:03d}")

    # ------------------------------------------------------------------
    # Home and park control
    # ------------------------------------------------------------------
    def park(self):
        """Park the mount (`:hP#`)."""
        self.send_command(":hP", expect_response=False)

    def unpark(self):
        """Unpark the mount (`:PO#`)."""
        self.send_command(":PO", expect_response=False)

    def seek_home(self):
        """Begin a homing sequence (`:hS#`)."""
        self.send_command(":hS", expect_response=False)

    def home_status(self) -> str:
        """Return the home position status (`:h?#`)."""
        return self.send_command(":h?")

    # ------------------------------------------------------------------
    # Limits / Safety
    # ------------------------------------------------------------------
    def get_lower_limit(self) -> str:
        """Get the lower altitude limit (`:Gl#`)."""
        return self.send_command(":Go")

    def get_upper_limit(self) -> str:
        return self.send_command(":Gh")

    def set_high_alt_limit(self, degrees: float) -> str:
        return self.send_command(f":Sh{degrees:+03.0f}")

    # ------------------------------------------------------------------
    # Time and date control
    # ------------------------------------------------------------------
    def get_local_time(self) -> str:
        """Return local time (`:GL#`)."""
        return self.send_command(":GL")

    def get_local_date(self) -> str:
        """Return local date (`:GC#`)."""
        return self.send_command(":GC")

    def get_julian_date(self) -> str:
        """Return Julian date (`:GJD#`)."""
        return self.send_command(":GJD")

    def set_local_time(self, hhmmss: str) -> str:
        """
        Set local time.

        Parameters
        ----------
        hhmmss : str
            Time in HH:MM:SS format.
        """
        return self.send_command(f":SL{hhmmss}")

    def set_local_date_time(self, date_iso: str, time_hms: str) -> str:
        """Set local date and time (`:SLDTyyyy-mm-dd,HH:MM:SS#`)."""
        return self.send_command(f":SLDT{date_iso},{time_hms}")

    def set_utc_date_time(self, date_iso: str, time_hms: str) -> str:
        """Set UTC date and time (`:SUDTyyyy-mm-dd,HH:MM:SS#`)."""
        return self.send_command(f":SUDT{date_iso},{time_hms}")

    def get_julian_ext(self) -> str:
        return self.send_command(":GJD1")

    def get_julian_with_flag(self) -> str:
        return self.send_command(":GJD2")

    def set_julian(self, jd_value: str) -> str:
        return self.send_command(f":SJD{jd_value}")

    # ------------------------------------------------------------------
    # Firmware and version info
    # ------------------------------------------------------------------
    def firmware_version(self) -> str:
        """Return firmware version (`:GVN#`)."""
        return self.send_command(":GVN")

    def firmware_date(self) -> str:
        """Return firmware build date (`:GVD#`)."""
        return self.send_command(":GVD")

    def product_name(self) -> str:
        """Return product name (`:GVP#`)."""
        return self.send_command(":GVP")

    def hardware_version(self) -> str:
        """Return hardware revision (`:GVZ#`)."""
        return self.send_command(":GVZ")

    def firmware_time(self) -> str:
        return self.send_command(":GVT")

    # ------------------------------------------------------------------
    # Networking and IP utilities
    # ------------------------------------------------------------------
    def get_ip_info(self) -> str:
        return self.send_command(":GIP")

    def get_wireless_ip(self) -> str:
        return self.send_command(":GIPW")

    def wireless_available(self) -> str:
        return self.send_command(":GWAV")

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------
    def start_log(self):
        return self.send_command(":startlog", expect_response=False)

    def stop_log(self):
        return self.send_command(":stoplog", expect_response=False)

    def get_event_log(self) -> str:
        return self.send_command(":evlog")

    # ------------------------------------------------------------------
    # Utility and conversion helpers
    # (DON'T NEED THESE THERE ARE ALREADY METHODS AT THE TOP FOR THIS)
    # ------------------------------------------------------------------
    # @staticmethod
    # def ra_to_hours(ra: str) -> float:
    #     """
    #     Convert RA string (HH:MM:SS.SS) to decimal hours.
    #     """
    #     m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)$", ra)
    #     if not m:
    #         raise ValueError(f"Invalid RA format: {ra}")
    #     hh, mm, ss = map(float, m.groups())
    #     return hh + mm / 60 + ss / 3600

    # @staticmethod
    # def dec_to_degrees(dec: str) -> float:
    #     """
    #     Convert DEC string (+DD:MM:SS.S) to decimal degrees.
    #     """
    #     m = re.match(r"^([+-]?\d{1,3}):(\d{2}):(\d{2}(?:\.\d+)?)$", dec)
    #     if not m:
    #         raise ValueError(f"Invalid DEC format: {dec}")
    #     deg, mm, ss = map(float, m.groups())
    #     sign = -1 if dec.startswith("-") else 1
    #     return sign * (abs(deg) + mm / 60 + ss / 3600)