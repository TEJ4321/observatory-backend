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
- There are tests for a number of the methods here, but NOT all have been tested yet.

Author: Tejas
License: MIT
"""
import time
import socket
import re
from typing import Tuple, Optional, Union, List

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
    >>> ra, dec = mount.get_mount_ra_dec()
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
        try:
            self.sock = socket.create_connection((self.host, self.port), self.timeout)
            self.sock.settimeout(self.timeout)
        except Exception as exc:
            raise MountError(f"Failed to connect: {exc}") from exc
        
        # Enable ultra-precision mode - documented as a command that requires no reply
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
    def send_command(
            self,
            cmd: str,
            *,
            expect_response: bool = True,
            terminated: bool = True,
            single_char: bool = False,
            max_bytes: int = 1024,
            timeout: Optional[float] = None,
            unterminated_timeout: float = 0.2
        ) -> str:
        """
        Send a raw command to the mount and read the response.

        Parameters
        ----------
        cmd : str
            The mount command string (without the trailing '#').
        expect_response : bool
            If False, return immediately after sending the command. (Default is True)
        terminated : bool
            If True, read until '#' terminator (protocol string replies).
        single_char : bool
            If True, expect a one-character reply like '0' or '1' (no '#').
            If both terminated and single_char are True, terminated takes precedence.
        max_bytes : int
            Max bytes to read for non-terminated replies.
        timeout : Optional[float]
            Override socket timeout for this command.
        unterminated_timeout : float
            For non-terminated replies, how long to wait for more data before concluding the reply is done.
            (Default is 0.2 seconds or 1/10th of the main timeout, whichever is larger.)

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
            raise MountError("Not connected to mount. Make sure IP and port are correct.")
        if timeout is None:
            timeout = self.timeout
        self.sock.settimeout(timeout)
        

        # Send command
        try:
            self.sock.sendall(f"{cmd}#".encode("ascii"))
        except Exception as e:
            raise MountError(f"Failed to send command {cmd}: {e}") from e
        
        if not expect_response:
            return ""
        
        # read according to deterministic expectation
        data = b""
        try:
            if terminated:
                # read until '#' arrives
                while not data.endswith(b"#"):
                    chunk = self.sock.recv(4096)
                    if not chunk:
                        break
                    data += chunk
            elif single_char:
                # read exactly one byte (or up to 4 bytes if device occasionally sends small messages)
                # use small blocking read; if the socket returns nothing or times out, raise.
                chunk = self.sock.recv(4)
                if not chunk:
                    raise MountError(f"No response for single-char command '{cmd}'")
                data += chunk[:1]  # only first significant char
            else:
                # variable-length non-terminated reply — read available bytes up to max_bytes,
                # stop when no more data arrives within a short timeout slice.
                # Use a short polling approach.
                total = 0
                # temporarily shorten timeout to avoid long blocking reads for non-terminated replies
                short_timeout = max(unterminated_timeout, timeout / 10 if timeout else unterminated_timeout)
                self.sock.settimeout(short_timeout)
                while total < max_bytes:
                    try:
                        chunk = self.sock.recv(4096)
                    except socket.timeout:
                        # no more data
                        break
                    if not chunk:
                        break
                    data += chunk
                    total += len(chunk)
                # restore timeout to the per-call timeout
                self.sock.settimeout(timeout if timeout else self.timeout)
        except socket.timeout:
            # If nothing was received at all, consider it a timeout error
            if not data:
                raise MountError(f"Timeout waiting for response to '{cmd}'")
            if terminated:
                raise MountError(f"Timeout waiting for terminator '#' in response to '{cmd}'")
            # else proceed with whatever we might have (partial response)
        except Exception as exc:
            raise MountError(f"Error receiving response to '{cmd}': {exc}") from exc

        # print(f"Raw data response from (`{cmd}#`): {data}")  # Debug print

        # Might be better to just change to errors=ignore, but this allows conversion of 0xDF to degree symbol
        text = data.decode("utf-8", errors="backslashreplace").replace("\\xdf", "°").replace("ß", "°")
        
        # print(f"DECODED DATA: {text}")  # Debug print
        
        # Handle multiple replies merged in one packet
        if "#" in text:
            text = text.split("#")[0] + "#"  # take only the first full reply
            
        # print(f"SPLIT UP DECODED DATA: {text}")  # Debug print
        
        # Trim terminator and whitespace
        text = text.rstrip("#").strip()
        
        # print(f"FINAL CLEANED DATA: {text}")  # Debug print
        
        return text
    

    # ------------------------------------------------------------------
    # Formatters and parsers
    # ------------------------------------------------------------------
    @staticmethod
    def _hours_to_hms(hours: float) -> str:
        """
        Convert decimal hours -> "HH:MM:SS.SS" string (zero-padded).
        Example: 12.5 -> "12:30:00.00"
        """
        h = int(hours)
        m = int((hours - h) * 60)
        s = (hours - h - m/60) * 3600
        return f"{h:02d}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _degrees_to_dms(deg: float, signed=True) -> str:
        """
        Convert decimal degrees -> "+DD:MM:SS.S" or "DDD:MM:SS.S" for azimuths.
        If signed=True, includes leading '+' or '-'.
        """
        sign = "-" if deg < 0 else "+"
        d = abs(int(deg))
        m = int((abs(deg) - d) * 60)
        s = (abs(deg) - d - m/60) * 3600
        if signed:
            return f"{sign}{d:02d}:{m:02d}:{s:05.2f}"
        return f"{d:03d}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _hms_to_hours(ra_str: str) -> float:
        """
        Convert "HH:MM:SS.SS" -> decimal hours (float).
        """
        h, m, s = map(float, re.split(r"[:]", ra_str))
        return h + m/60 + s/3600

    @staticmethod
    def _dms_to_degrees(dec_str: str) -> float:
        """
        Convert "+DD:MM:SS.S" or "DDD:MM:SS.S" (optionally with leading sign) -> decimal degrees.
        """
        sign = -1 if dec_str.strip().startswith("-") else 1
        d, m, s = map(float, re.split(r"[:]", dec_str.strip("+-")))
        return sign * (abs(d) + m/60 + s/3600)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    
    def get_status_code(self) -> str:
        """Return the raw status code (`:Gstat#`)."""
        # return self.send_command(":Gstat")
        return self.send_command(":Gstat", expect_response=True, terminated=True, single_char=False)

    def get_status(self) -> str:
        """Returns human-readable mount status from (`:Gstat#`)."""
        code = self.get_status_code()
        return self.STATUS_CODES.get(code, f"Unknown status code ({code})")

    def is_tracking(self) -> bool:
        """
        Returns the mount's currently tracking status(`:GTRK#`).
        
        Notes
        ----------
        Does not terminate with #
        """
        return self.send_command(":GTRK", single_char=True, terminated=False) == '1'
    
    def target_trackable(self) -> bool:
        """
        Returns whether the target is trackable or not - the tracking status of the target (`:GTTRK#`).
        
        Returns
        -------
        str
        - '0' if the target object is located in a position where tracking is not allowed (i.e. below the horizon, or above +89° if using an altazimuth mount)
        - '1' if the target object is located in a position where tracking is allowed.
            
        Notes
        ----------
        Does not terminate with #
        """
        return self.send_command(":GTTRK", single_char=True, terminated=False) == '1'

    def is_ready(self) -> bool:
        """
        NOTE: MIGHT NEED TO EDIT THIS (DEPRECATED?)
        
        Check if mount can accept slews (status codes 0 - tracking or 7 - idle).
        
        Use get_status_code method to be exact.
        """
        
        code = self.get_status_code()
        return code in ("0", "7")  # Tracking or idle

    def pier_side(self) -> str:
        """
        Return the current pier side (`:pS#`).

        Returns
        -------
        str
            'East' for east, 'West' for west.
        """
        return self.send_command(":pS", expect_response=True, terminated=True)

    def get_element_temperature(self, element: int) -> Union[str, float]:
        """
        Get the temperature of element n with (`:GTMPn#`).
        
        Args
        ----------
        element : int
            Element options:
            - 1 Right Ascension/Azimuth motor driver
            - 2 Declination/Altitude motor driver
            - 7 Right Ascension/Azimuth motor
            - 8 Declination/Altitude motor
            - 9 Electronics box temperature sensor
            - 11 Keypad (v2) display sensor
            - 12 Keypad (v2) PCB sensor
            - 13 Keypad (v2) controller sensor

        Returns
        --------
        str: +TTT.T#
            The required temperature in degrees Celsius (°C).
            If the required temperature cannot be read, the string “Unavailable” is returned.
        """
        
        temp = self.send_command(f":GTMP{element}", expect_response=True, terminated=True)
        
        if temp != "Unavailable":
            try:
                temp = float(temp)
                return temp
            except ValueError:
                pass
            raise MountError("Unknown temperature format")
        else:
            return temp
    
    def start_tracking(self):
        """Enable tracking (`:AP#`)."""
        self.send_command(":AP", expect_response=False)
        
    def stop_tracking(self):
        """Disable tracking (`:AL#`)."""
        self.send_command(":AL", expect_response=False)

    # ------------------------------------------------------------------
    # Firmware and version info
    # ------------------------------------------------------------------
    
    def firmware_date(self) -> str:
        """Return firmware build date (`:GVD#`)."""
        return self.send_command(":GVD", expect_response=True, terminated=True)
    
    def firmware_number(self) -> str:
        """Return firmware number (`:GVN#`)."""
        return self.send_command(":GVN", expect_response=True, terminated=True)

    def product_name(self) -> str:
        """Return product name (`:GVP#`)."""
        return self.send_command(":GVP", expect_response=True, terminated=True)

    def firmware_time(self) -> str:
        """Get firmware time (`:GVT#`)."""
        return self.send_command(":GVT", expect_response=True, terminated=True)
    
    def hardware_version(self) -> str:
        """Get hardware control box version (`:GVZ#`)."""
        return self.send_command(":GVZ", expect_response=True, terminated=True)

    # ------------------------------------------------------------------
    # Mount Position Getters
    # ------------------------------------------------------------------

    def get_mount_ra(self) -> str:
        """Return the current Right Ascension of the mount (`:GR#`)."""
        return self.send_command(":GR", expect_response=True, terminated=True)

    def get_mount_dec(self) -> str:
        """Return the current Declination of the mount (`:GD#`)."""
        return self.send_command(":GD", expect_response=True, terminated=True)
    
    def get_mount_ra_dec(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return current RA and Dec in a tuple containing two strings or floats depending on as_float.
        
        - Strings: "HH:MM:SS.SS", "+DD:MM:SS.S"
        - Floats: decimal hours, decimal degrees

        Parameters
        ----------
        as_float : bool
            If True, return (hours, degrees) as floats.
        """
        ra = self.get_mount_ra()
        dec = self.get_mount_dec()
        if as_float:
            return self._hms_to_hours(ra), self._dms_to_degrees(dec)
        return ra, dec
    
    def get_mount_alt(self) -> str:
        """Return current Altitude of the mount (`:GA#`)."""
        return self.send_command(":GA", expect_response=True, terminated=True)

    def get_mount_az(self) -> str:
        """Return current Azimuth of the mount (`:GZ#`)."""
        return self.send_command(":GZ", expect_response=True, terminated=True)

    def get_mount_alt_az(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return current Alt and Az in a tuple containing two strings or floats depending on as_float.

        - Strings: "+DD:MM:SS.S", "DDD:MM:SS.S"
        - Floats: decimal degrees, decimal degrees
        
        Parameters
        ----------
        as_float : bool
            If True, return (degrees, degrees) as floats.
        """
        alt = self.get_mount_alt()
        az = self.get_mount_az()
        if as_float:
            return self._dms_to_degrees(alt), self._dms_to_degrees(az)
        return alt, az
    
    # ------------------------------------------------------------------
    # Target Position Getters
    # ------------------------------------------------------------------
    
    def get_target_ra(self) -> str:
        """
        Return the current target Right Ascension - whether the mount is tracking the target or not (`:Gr#`).
        
        - If target set using equatorial coordinates, returns the target RA.
        - If target set using Alt/Az coordinates, returns the RA calculated from Alt/Az currently.
        - If no target is set, returns nothing.
        """
        return self.send_command(":Gr", expect_response=True, terminated=True)
    
    def get_target_dec(self) -> str:
        """
        Return the current target Declination - whether the mount is tracking the target or not (`:Gd#`).
        
        - If target set using equatorial coordinates, returns the target Dec.
        - If target set using Alt/Az coordinates, returns the Dec calculated from Alt/Az currently.
        - If no target is set, returns nothing.
        """
        return self.send_command(":Gd", expect_response=True, terminated=True)
    
    def get_target_ra_dec(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return target RA and Dec in a tuple containing two strings or floats depending on as_float.
        
        - Strings: "HH:MM:SS.SS", "+DD:MM:SS.S"
        - Floats: decimal hours, decimal degrees

        Parameters
        ----------
        as_float : bool
            If True, return (hours, degrees) as floats.
            
        Notes
        ----------
        If no target is set, returns nothing.
        """
        ra = self.get_target_ra()
        dec = self.get_target_dec()
        if as_float:
            return self._hms_to_hours(ra), self._dms_to_degrees(dec)
        return ra, dec
    
    def get_target_alt(self) -> str:
        """
        Return the current target Altitude for the next slew (`:Ga#`).
        
        - If target set using Alt/Az coordinates, returns the target Alt.
        - If target set using equatorial coordinates, returns the Alt calculated from RA/Dec currently.
        - If no target is set, returns nothing.
        """
        return self.send_command(":Ga", expect_response=True, terminated=True)
    
    def get_target_az(self) -> str:
        """
        Return the current target Azimuth for the next slew (`:Gz#`).
        
        - If target set using Alt/Az coordinates, returns the target Az.
        - If target set using equatorial coordinates, returns the Az calculated from RA/Dec currently.
        - If no target is set, returns nothing.
        """
        return self.send_command(":Gz", expect_response=True, terminated=True)
    
    def get_target_alt_az(self, as_float=False) -> Tuple[Union[str, float], Union[str, float]]:
        """
        Return target Alt and Az in a tuple containing two strings or floats depending on as_float.

        - Strings: "+DD:MM:SS.S", "DDD:MM:SS.S"
        - Floats: decimal degrees, decimal degrees
        
        Parameters
        ----------
        as_float : bool
            If True, return (degrees, degrees) as floats.
            
        Notes
        ----------
        If no target is set, returns nothing.
        """
        alt = self.get_target_alt()
        az = self.get_target_az()
        if as_float:
            return self._dms_to_degrees(alt), self._dms_to_degrees(az)
        return alt, az
    
    # ------------------------------------------------------------------
    # Target Position Setters
    # ------------------------------------------------------------------
    
    def set_target_ra(self, ra: Union[str, float]) -> str:
        """
        Set target Right Ascension for a future slew.

        Parameters
        ----------
        ra : str or float
            Right ascension in 'HH:MM:SS' or decimal hours.
        
        Returns
        ----------
        str
            '0' if RA was invalid, '1' if valid.
        """
        if isinstance(ra, (int, float)):
            ra = self._hours_to_hms(ra)
        return self.send_command(f":Sr{ra}", expect_response=True, terminated=False, single_char=True)
    
    def set_target_dec(self, dec: Union[str, float]) -> str:
        """
        Set target Declination for a future slew.

        Parameters
        ----------
        dec : str or float
            Declination in '+DD:MM:SS' or decimal degrees.
        
        Returns
        ----------
        str
            '0' if Dec was invalid, '1' if valid.
        """
        if isinstance(dec, (int, float)):
            dec = self._degrees_to_dms(dec, signed=True)
        return self.send_command(f":Sd{dec}", expect_response=True, terminated=False, single_char=True)
    
    def set_target_ra_dec(self, ra: Union[str, float], dec: Union[str, float]) -> dict:
        """
        Set target RA/Dec coordinates for a slew.

        Parameters
        ----------
        ra : str or float
            Right ascension in 'HH:MM:SS' or decimal hours.
        dec : str or float
            Declination in '+DD:MM:SS' or decimal degrees.
        
        Returns
        -------
        dict
            Dictionary with 'ra' and 'dec' keys indicating success ('1') or failure ('0').
        """
        return {
            "ra": self.set_target_ra(ra),
            "dec": self.set_target_dec(dec)
        }

    def set_target_alt(self, alt: Union[str, float]) -> str:
        """
        Set target Altitude for a future slew.

        Parameters
        ----------
        alt : str or float
            Altitude in '+DD:MM:SS' or decimal degrees.
        
        Returns
        ----------
        str
            '0' if Alt is outside the slew range, '1' if object within slew range.
        """
        if isinstance(alt, (int, float)):
            alt = self._degrees_to_dms(alt, signed=True)
        return self.send_command(f":Sa{alt}", expect_response=True, terminated=False, single_char=True)

    def set_target_az(self, az: Union[str, float]) -> str:
        """
        Set target Azimuth for a future slew.

        Parameters
        ----------
        az : str or float
            Azimuth in 'DDD:MM:SS' or decimal degrees.
        
        Returns
        ----------
        str
            '0' if Az was invalid, '1' if valid.
        """
        if isinstance(az, (int, float)):
            az = self._degrees_to_dms(az, signed=False)
        return self.send_command(f":Sz{az}", expect_response=True, terminated=False, single_char=True)

    def set_target_alt_az(self, alt: Union[str, float], az: Union[str, float]) -> dict:
        """
        Set target Alt/Az coordinates for a slew.

        Parameters
        ----------
        alt : str or float
            Altitude in '+DD:MM:SS' or decimal degrees.
        az : str or float
            Azimuth in 'DDD:MM:SS' or decimal degrees.
        
        Returns
        -------
        dict
            Dictionary with 'alt' and 'az' keys indicating success ('1') or failure ('0').
        """
        return {
            "alt": self.set_target_alt(alt),
            "az": self.set_target_az(az)
        }

    # ------------------------------------------------------------------
    # Slew commands
    # ------------------------------------------------------------------

    def slew_to_target_equatorial(self, pier_side: Optional[str]) -> str:
        """
        Slew to the previously set RA/Dec target (`:MS#`) and start tracking the target.
        
        Parameters
        ----------
        pier_side : Optional[str]
            Desired pier side for the slew: {'E', 'W'}.
            - If None, mount chooses automatically (DEFAULT)
            - E: East side of pier.
            - W: West side of pier.

        Returns
        -------
        str
            '0' if no error, and a human-readable message if there is an error.
        """
        if pier_side is not None and pier_side != "" and pier_side not in {"E", "W", "e", "w"}:
            raise ValueError("Pier side must be one of E, W")
        if pier_side == "E" or pier_side == "e":
            return self.send_command(f":MSfs3", expect_response=False, terminated=False)
        if pier_side == "W" or pier_side == "w":
            return self.send_command(f":MSfs2", expect_response=False, terminated=False)
        return self.send_command(":MS", expect_response=True, terminated=False)

    def slew_to_target_altaz(self) -> str:
        """
        Slew to the previously set Alt/Az target (`:MA#`) and DON'T TRACK the target.

        Returns
        -------
        str
            '0' if no error, and a human-readable message if there is an error.
        """
        return self.send_command(":MA", expect_response=False, terminated=False)
    
    def set_max_slew_rate(self, rate: int) -> str:
        """
        Set the maximum slew rate to "rate" degrees per second (`:Sw{rate}#`).

        Args:
            rate (int): Maximum slew rate

        Returns
        -------
        str:
            '0' if rate is invalid, '1' if valid.
        """
        return self.send_command(f":Sw{rate}", expect_response=True, terminated=False, single_char=True)
    
    # ------------------------------------------------------------------
    # Movement and motion control
    # ------------------------------------------------------------------
    
    def stop_all_movement(self):
        """Immediately stop ALL movement including slewing, parking and tracking (`:STOP#`)."""
        self.send_command(":STOP", expect_response=False)

    def halt_movement(self, direction: Optional[str] = None):
        """
        Halts all current slewing (`:Q#`). Also supports halting movement in only one direction, but halts all movement by default.
        
        Parameters
        ----------
        direction : Optional[str]
        
            Direction to halt slewing in: {'N', 'S', 'E', 'W'}.
            - If None, halts all slewing in all directions.
            - N: Halt northward (for equatorial mounts) or upward (for altazimuth mounts) movements.
            - S: Halt southward (for equatorial mounts) or downward (for altazimuth mounts) movements.
            - E: Halt eastward (for equatorial mounts) or leftward (for altazimuth mounts) movements.
            - W: Halt westward (for equatorial mounts) or rightward (for altazimuth mounts) movements.
        """
        if direction is not None and direction not in {"N", "S", "E", "W", "n", "s", "e", "w"}:
            raise ValueError("Direction must be one of N, S, E, W")
        if direction is not None:
            self.send_command(f":Q{direction.lower()}", expect_response=False)

    def move_direction(self, direction: str):
        """
        Start manual movement in a cardinal direction.

        Parameters
        ----------
        direction : str 
        
            Direction to start moving in: {'N', 'S', 'E', 'W'}.
            - N: Move northward (for equatorial mounts) or upward (for altazimuth mounts) movements.
            - S: Move southward (for equatorial mounts) or downward (for altazimuth mounts) movements.
            - E: Move eastward (for equatorial mounts) or leftward (for altazimuth mounts) movements.
            - W: Move westward (for equatorial mounts) or rightward (for altazimuth mounts) movements.
        """
        direction = direction.upper()
        if direction not in {"N", "S", "E", "W", "n", "s", "e", "w"}:
            raise ValueError("Direction must be one of N, S, E, W")
        self.send_command(f":M{direction.lower()}", expect_response=False)

    def nudge(self, direction: str, ms: int):
        """
        Nudge the mount in a cardinal direction for a specified duration.

        Parameters
        ----------
        direction : str
            Direction to nudge in: {'N', 'S', 'E', 'W'}.
            - N: Nudge northward (for equatorial mounts) or upward (for altazimuth mounts) movements.
            - S: Nudge southward (for equatorial mounts) or downward (for altazimuth mounts) movements.
            - E: Nudge eastward (for equatorial mounts) or leftward (for altazimuth mounts) movements.
            - W: Nudge westward (for equatorial mounts) or rightward (for altazimuth mounts) movements.
        ms : int
            Duration of the nudge in milliseconds.
        """
        direction = direction.upper()
        if direction not in {"N", "S", "E", "W", "n", "s", "e", "w"}:
            raise ValueError("Direction must be one of N, S, E, W")
        if ms <= 0:
            raise ValueError("Duration must be a positive integer")
        
        self.move_direction(direction)
        time.sleep(ms / 1000.0)
        self.halt_movement(direction)

    def flip(self) -> str:
        """
        Flip the mount to the opposite pier side (`:FLIP#`).
        
        This command acts in different ways on the AZ2000 and german equatorial (GM1000 - GM4000) mounts.
        - On an AZ2000 mount:
            - When observing an object near the lowest culmination, requests to make a 360° turn of the azimuth axis and point the object again.
        - On a german equatorial mount:
            - When observing an object near the meridian, requests to make a 180° turn of the RA axis and move the declination axis in order to point the object with the telescope on the other side of the mount.
        
        Returns
        -------
        str
            '0' if flip not possible at this time, '1' if flip successful
        """
        return self.send_command(":FLIP", expect_response=True, terminated=False, single_char=True)

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
        return self.send_command(":h?", expect_response=True, terminated=False, single_char=True)

    # ------------------------------------------------------------------
    # Limits / Safety
    # ------------------------------------------------------------------
    
    def get_lower_limit(self) -> str:
        """
        Get lower limit (`:Gl#`).
        
        Returns the lowest altitude above the horizon that the mount will be allowed to slew to without reporting an error message .
        
        Returns
        -------
        str
            Signed lower limit in degrees (e.g., "+10" for 10°).
        """
        return self.send_command(":Go", expect_response=True, terminated=True)

    def get_upper_limit(self) -> str:
        """
        Get upper limit (`:Gh#`).
        
        Returns the highest altitude above the horizon that the mount will be allowed to slew to without reporting an error message .
        
        Returns
        -------
        str
            Signed upper limit in degrees (e.g., "+85" for 85°).
        """
        return self.send_command(":Gh", expect_response=True, terminated=True)

    def set_high_alt_limit(self, degrees: int) -> str:
        """
        Set upper altitude limit (`:Sh+{degrees}#`).
        
        This is the highest altitude above the horizon that the mount will be allowed to slew to without reporting an error message.

        Args:
            degrees (int): altitude limit in degrees (0 to 90)

        Raises:
            ValueError: When degrees is out of range.

        Returns:
            str: '0' if setting is invalid, '1' if setting is valid.
        """
        
        if degrees < 0 or degrees > 90:
            raise ValueError("Upper limit must be between 0 and 90 degrees")
        return self.send_command(f":Sh+{degrees}", terminated=False, single_char=True)

    # ------------------------------------------------------------------
    # Time and date control
    # ------------------------------------------------------------------
    
    def get_local_time(self) -> str:
        """
        Return local time (`:GL#`).
        
        Returns time in HH:MM:SS.SS format.
        """
        return self.send_command(":GL", expect_response=True, terminated=True)

    def get_current_date(self) -> str:
        """
        Return current date (`:GC#`).
        
        Returns date in YYYY-MM-DD format.
        """
        return self.send_command(":GC", expect_response=True, terminated=True)

    def get_local_date_time(self) -> Tuple[str, str]:
        """
        Return local date and time (`:GLDT#`).
        
        Returns a tuple of (date, time) in (YYYY-MM-DD, HH:MM:SS.SS) format.
        """
        response = self.send_command(":GLDT", expect_response=True, terminated=True)
        date_str, time_str = response.split(",")
        return date_str, time_str
    
    def get_utc_date_time(self) -> Tuple[str, str]:
        """
        Return UTC date and time (`:GUDT#`).
        
        Returns a tuple of (date, time) in (YYYY-MM-DD, HH:MM:SS.SS) format.
        """
        response = self.send_command(":GUDT", expect_response=True, terminated=True)
        date_str, time_str = response.split(",")
        return date_str, time_str
    
    def get_utc_offset(self) -> str:
        """
        Return the current UTC offset (`:GG#`).
        
        Returns
        -------
        str
            Signed UTC offset in sHH:MM:SS.S format (e.g., "+05:30:00.0" for UTC+5:30).
        """
        return self.send_command(":GG", expect_response=True, terminated=True)
    
    def get_sidereal_time(self) -> str:
        """
        Return local sidereal time (`:GS#`).
        
        Returns time in HH:MM:SS.SS format.
        """
        return self.send_command(":GS", expect_response=True, terminated=True)
    
    def get_julian_date(self, extra_precision: bool = False, leap_seconds: bool = False) -> str:
        """
        Return Julian date (`:GJD#`).
        
        Parameters
        ----------
        extra_precision : bool (default False)
            If True, returns with 3 extra decimal places of precision
            - Normal Precision: 5 decimal places
            - Extra Precision:  8 decimal places
        leap_seconds : bool (default False)
            If True, forces extra precision and includes leap seconds in the calculation, with
            an optional "L" appended at the end to signal that we are in a leap second.
        
        Returns
        ----------
        str
            Julian date string in one of the following formats:
            - `JJJJJJJ.JJJJJ` if no flags
            - `JJJJJJJ.JJJJJJJJ` if extra_precision is True
            - `JJJJJJJ.JJJJJJJJ` or `JJJJJJJ.JJJJJJJJL` if leap second is included 

        """
        if leap_seconds:
            return self.send_command(":GJD2")
        elif extra_precision:
            return self.send_command(":GJD1")
        else:
            return self.send_command(":GJD")

    def set_local_time(self, time_hms: str) -> str:
        """
        Set local time (`SL{time_hms}#`).

        Parameters
        ----------
        hhmmss : str
            Time in HH:MM:SS.SS format.
        """
        return self.send_command(f":SL{time_hms}", terminated=False, single_char=True)

    def set_local_date_time(self, date_iso: str, time_hms: str) -> str:
        """
        Set local date and time together (`:SLDT{date_iso,time_hms}#`).
        - Local Time: HH:MM:SS (hours, minutes, seconds)
        - Local date to YYYY-MM-DD (year, month, day of month).
        
        Parameters
        ----------
        date_iso : str
            Date in YYYY-MM-DD format or MM/DD/YYYY or MM/DD/YY (from 2000).
        time_hms : str
            Time in HH:MM:SS format, optionally with up to 2 decimal places of seconds.
        """
        return self.send_command(f":SLDT{date_iso},{time_hms}", terminated=False, single_char=True)
    
    def set_utc_date_time(self, date_iso: str, time_hms: str) -> str:
        """
        Set UTC date and time together (`:SUDT{date_iso,time_hms}#`).
        - UTC Time: HH:MM:SS (hours, minutes, seconds)
        - UTC date to YYYY-MM-DD (year, month, day of month).
        
        Parameters
        ----------
        date_iso : str
            Date in YYYY-MM-DD format or MM/DD/YYYY or MM/DD/YY (from 2000).
        time_hms : str
            Time in HH:MM:SS format, optionally with up to 2 decimal places of seconds.
        """
        return self.send_command(f":SUDT{date_iso},{time_hms}", terminated=False, single_char=True)

    def set_julian_date(self, jd_value: str) -> str:
        """
        Set Julian date (`:SJD{jd_value}#`) to given value up to 8 decimal places.
        
        Parameters
        ----------
        jd_value : str
            Julian date string in the format `JJJJJJJ.JJJJJ` or `JJJJJJJ.JJJJJJJJ`.
        """
        return self.send_command(f":SJD{jd_value}", terminated=False, single_char=True)

    def adjust_mount_time(self, ms: int) -> bool:
        """
        Adjust the mount's time by a specified signed number of milliseconds (`:NUtim{ms}#`).
        
        Parameters
        ----------
        ms : int
            Number of milliseconds to adjust the time by (positive or negative).
        
        Returns
        -------
        bool
            True if adjustment was successful, False otherwise.
        """
        if ms < -999 or ms > 999:
            raise ValueError("Milliseconds adjustment must be between -999 and 999")
        
        return self.send_command(f":AT{ms}", expect_response=True, terminated=True) == '1'

    # ------------------------------------------------------------------
    # Networking and IP utilities
    # ------------------------------------------------------------------
    def get_connection_type(self) -> str:
        """
        Get the current connection type of the mount (`:GINQ#`).
        
        Returns
        -------
        str
            A string describing the connection type:
            - 'Serial RS-232'
            - 'GPS or GPS/RS-232'
            - 'Cabled LAN'
            - 'Wireless LAN'
            - 'Unknown' if the code is not recognized.
        """
        code = self.send_command(":GINQ", expect_response=True, terminated=True)
        if code == "0":
            return "Serial RS-232"
        elif code == "1":
            return "GPS or GPS/RS-232"
        elif code == "2":
            return "Cabled LAN"
        elif code == "3":
            return "Wireless LAN"
        else:
            raise MountError(f"Unknown connection type code: {code}")
        
    
    def get_ip_info(self, wireless: bool = False) -> Tuple[str, str, str, bool]:
        """
        Get the all IP information about the mount (`:GIP#`).
        
        Alternatively, get the wireless IP information about the mount (`:GIPW#`) based on wireless flag.

        Returns: nnn.nnn.nnn.nnn,mmm.mmm.mmm.mmm,ggg.ggg.ggg.ggg,c#
        A string containing the IP address (nnn.nnn.nnn.nnn), the subnet mask
        (mmm.mmm.mmm.mmm), the gateway (ggg.ggg.ggg.ggg) and a character (c) that is
        set to “D” if the address is obtained from a DHCP server, or “M” if the address is
        configured manually.
        
        Parameters
        ----------
        wireless : bool
            If True, get the wireless IP address instead (`:GIPW#`).
        
        Returns
        ----------
        Tuple : [ip: str, subnet: str, gateway: str, dhcp: bool]
            - ip: IPv4 address as string (nnn.nnn.nnn.nnn)
            - subnet: Subnet mask (IPv4) as string (mmm.mmm.mmm.mmm)
            - gateway: Gateway IPv4 address as string (ggg.ggg.ggg.ggg)
            - dhcp: True if using DHCP, False if using manual configuration
        """

        if wireless:
            networkstats = self.send_command(":GIPW", expect_response=True, terminated=True)
        else:
            networkstats = self.send_command(":GIP", expect_response=True, terminated=True)
            
        ip, subnet, gateway, dhcp = networkstats.split(",")
        
        # Convert DHCP/Manual flag to boolean
        if dhcp not in {"D", "M"}:
            raise MountError(f"Unexpected DHCP/Manual flag in response: {dhcp}")
        elif dhcp == "M":
            dhcp = False
        else:
            dhcp = True
            
        return ip, subnet, gateway, dhcp

    def scan_wireless(self) -> bool:
        """
        Start scanning for wireless access points (`:GWRSC#`).
        
        Call the wireless_access_points method (`:GWRAP2#`) to get the results of the scan.

        Returns:
            bool: True if wireless adapter is available, False otherwise.
        """
        return self.send_command(":GWRSC", expect_response=True, terminated=True) == '1'
    
    def wireless_access_points(self) -> List[Tuple[str, str]]:
        """
        Get the wireless access points available with encryption information (`:GWRAP2#`).
        
        Returns
        ----------
        List: [Tuple[str, str]]
            A list of tuples containing (SSID, Security Type).
            - Example: [("MyWiFi", "WPA2"), ("GuestNetwork", "Open")]
        """
        response = self.send_command(":GWRAP2", expect_response=True, terminated=True)
        
        if response == "0":
            return []  # No wireless available
        status = response[0]
        if status == "1":
            raise MountError("Wireless access point scan is still underway.")
        if status != "2":
            raise MountError(f"Unexpected response status: {status}")
        
        access_points = []
        entries = response[1:].split(",")  # Exclude status
        
        for entry in entries:
            if len(entry) < 2:
                continue  # Skip invalid entries
            security_code = entry[0]
            ssid = entry[1:]
            
            security_type = {
                'o': 'Open',
                'w': 'WEP',
                '1': 'WPA',
                '2': 'WPA2',
                'x': 'Unsupported'
            }.get(security_code, 'Unknown')
            
            access_points.append((ssid, security_type))
        
        return access_points

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------
    def start_log(self):
        """
        Request the mount to start logging events to its internal memory (`:startlog#`).
        
        Access the event log using the get_event_log method (`:evlog#`) or get_communication_log method (`:getlog#`).
        """
        return self.send_command(":startlog", expect_response=False)

    def stop_log(self):
        """
        Request the mount to stop logging events to its internal memory (`:stoplog#`).
        
        Access the event log using the get_event_log method (`:evlog#`) or get_communication_log method (`:getlog#`).
        """
        return self.send_command(":stoplog", expect_response=False)

    def get_event_log(self) -> str:
        """
        Get the event log from the mount's internal memory (`:evlog#`).
        
        Returns a string containing the event log entries (up to 3Kbytes).
        """
        return self.send_command(":evlog", expect_response=True, terminated=False, max_bytes=3100)
    
    def get_communication_log(self) -> str:
        """
        Get the communication log from the mount's internal memory (`:getlog#`).
        
        Returns a string containing the communication log entries (up to 256Kbytes).
        """
        return self.send_command(":getlog", expect_response=True, terminated=False, max_bytes=262144)

if __name__ == "__main__":
    # Example usage
    mount = TenMicronMount("192.168.1.10", port=3492)
    mount.connect()

    # Status
    print("\n===================================")
    print("Status")
    print("===================================")
    print("Status Code:", mount.get_status_code())
    print("Status:", mount.get_status())
    print("Tracking: ", mount.is_tracking())
    print("Target Trackable: ", mount.target_trackable())
    print("Is Ready for Slew:", mount.is_ready())
    print("Pier Side:", mount.pier_side())
    
    # Firmware and version info
    print("\n===================================")
    print("Firmware and version info")
    print("===================================")
    print("Firmware Date:", mount.firmware_date())
    print("Firmware Number:", mount.firmware_number())
    print("Product Name:", mount.product_name())
    print("Firmware Time:", mount.firmware_time())
    print("Hardware Version:", mount.hardware_version())
    
    # Mount Position Getters
    print("\n===================================")
    print("Mount Position Getters")
    print("===================================")
    print("Current RA:", mount.get_mount_ra())
    print("Current Dec:", mount.get_mount_dec())
    print("Current RA/Dec:", mount.get_mount_ra_dec())
    print("Current RA/Dec (float):", mount.get_mount_ra_dec(as_float=True))
    print("Current Alt:", mount.get_mount_alt())
    print("Current Az:", mount.get_mount_az())
    print("Current Alt/Az:", mount.get_mount_alt_az())
    print("Current Alt/Az (float):", mount.get_mount_alt_az(as_float=True))
    
    # Target Position Getters
    print("\n===================================")
    print("Target Position Getters")
    print("===================================")
    print("Target RA:", mount.get_target_ra())
    print("Target Dec:", mount.get_target_dec())
    print("Target RA/Dec:", mount.get_target_ra_dec())
    print("Target RA/Dec (float):", mount.get_target_ra_dec(as_float=True))
    print("Target Alt:", mount.get_target_alt())
    print("Target Az:", mount.get_target_az())
    print("Target Alt/Az:", mount.get_target_alt_az())
    print("Target Alt/Az (float):", mount.get_target_alt_az(as_float=True))
    
    
    
    mount.close()