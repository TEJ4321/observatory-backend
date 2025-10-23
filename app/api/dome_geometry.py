import numpy as np
from astropy.coordinates import EarthLocation, SkyCoord, AltAz
from astropy.time import Time
import astropy.units as u


class DomeGeometry:
    """
    Calculates the required dome azimuth to keep the telescope's view
    unobstructed for an off-center German Equatorial Mount.
    """

    def __init__(
        self,
        # Observatory Location
        latitude: float,
        longitude: float,
        elevation: float,
        # Dome Configuration
        dome_radius: float,
        # Mount Configuration
        mount_offset_ns: float,  # North-South offset from dome center
        mount_offset_ew: float,  # East-West offset from dome center
        mount_pier_height: float, # Height of the RA axis pivot from the floor
        polar_axis_to_dec_axis: float, # Distance from RA axis pivot to Dec axis
        dec_axis_to_telescope: float, # Distance from Dec axis to telescope optical axis
    ):
        self.location = EarthLocation.from_geodetic(
            lat=latitude * u.deg, lon=longitude * u.deg, height=elevation * u.m
        )
        self.dome_radius = dome_radius
        self.mount_offset_ns = mount_offset_ns
        self.mount_offset_ew = mount_offset_ew
        self.mount_pier_height = mount_pier_height
        self.polar_axis_to_dec_axis = polar_axis_to_dec_axis
        self.dec_axis_to_telescope = dec_axis_to_telescope
        self.latitude_rad = np.deg2rad(latitude)

    def calculate_dome_azimuth(
        self,
        ra_hours: float,
        dec_degrees: float,
        sidereal_time_hours: float,
        pier_side: str,
    ) -> float:
        """
        Calculates the optimal dome azimuth for the given telescope pointing.

        The calculation is done in a local horizon coordinate system:
        - Origin: Center of the dome on the floor.
        - +X: East
        - +Y: Up (Zenith)
        - +Z: South

        Args:
            ra_hours (float): Telescope's Right Ascension in decimal hours.
            dec_degrees (float): Telescope's Declination in decimal degrees.
            sidereal_time_hours (float): Current local sidereal time in decimal hours.
            pier_side (str): The pier side of the mount ('East' or 'West').

        Returns:
            float: The calculated dome azimuth in degrees.
        """
        # 1. Calculate Hour Angle and convert angles to radians
        ha_rad = np.deg2rad((sidereal_time_hours - ra_hours) * 15)
        dec_rad = np.deg2rad(dec_degrees)
        pier_flip = np.pi if pier_side.lower() == "east" else 0

        # 2. Define the mount's RA axis pivot point in the dome's local frame
        # Note: The dome center is at (0, 0, 0)
        ra_pivot_pos = np.array([
            self.mount_offset_ew,
            self.mount_pier_height,
            self.mount_offset_ns
        ])

        # 3. Calculate the position of the telescope's optical axis pivot point
        # This involves a series of rotations from the mount's base.

        # Rotation for latitude tilt
        lat_rot = np.array([
            [1, 0, 0],
            [0, np.cos(-self.latitude_rad), -np.sin(-self.latitude_rad)],
            [0, np.sin(-self.latitude_rad), np.cos(-self.latitude_rad)]
        ])

        # Vector from RA pivot to Dec pivot along the polar axis
        v_ra_to_dec = np.array([0, self.polar_axis_to_dec_axis, 0])
        dec_pivot_pos_mount_frame = np.dot(lat_rot, v_ra_to_dec)

        # Rotation for Hour Angle (around polar axis, which is local Y after lat tilt)
        ha_rot = np.array([
            [np.cos(ha_rad), 0, np.sin(ha_rad)],
            [0, 1, 0],
            [-np.sin(ha_rad), 0, np.cos(ha_rad)]
        ])
        dec_pivot_pos_mount_frame = np.dot(ha_rot, dec_pivot_pos_mount_frame)

        # Vector from Dec pivot to telescope optical axis
        # This vector is perpendicular to the polar axis and rotates with Dec.
        # The pier flip and declination rotations happen around the Dec axis.
        v_dec_to_ota = np.array([np.cos(dec_rad + pier_flip), 0, np.sin(dec_rad + pier_flip)]) * self.dec_axis_to_telescope
        
        # Rotate this vector by HA and Latitude to bring it into the local horizon frame
        ota_offset_vec = np.dot(lat_rot, np.dot(ha_rot, v_dec_to_ota))

        # Final telescope position in the dome
        telescope_pos = ra_pivot_pos + dec_pivot_pos_mount_frame + ota_offset_vec

        # 4. Calculate the azimuth of the telescope's position vector
        # Azimuth is angle in X-Z plane, measured from North (our -Z) clockwise.
        # We calculate from +X (East) and adjust.
        az_rad = np.arctan2(telescope_pos[0], -telescope_pos[2]) # atan2(x, -z)
        az_deg = (np.rad2deg(az_rad) + 360) % 360

        return az_deg