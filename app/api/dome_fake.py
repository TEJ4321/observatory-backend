import asyncio
import time
from .dome_geometry import DomeGeometry
from .tenmicron.tenmicron_fake import TenMicronMountFake # To get telescope state

class DomeError(Exception):
    """Custom exception for Dome communication errors."""
    pass

class DomeFake:
    """
    A fake class that mimics a dome controller for testing purposes.
    It manages its own state for azimuth, movement, and synchronization.
    """
    def __init__(self, mount: TenMicronMountFake):
        self._is_connected: bool = False
        self._azimuth: float = 180.0
        self._is_moving: bool = False
        self._is_syncing: bool = False
        self._target_azimuth: float = 180.0
        self._start_azimuth: float = 180.0
        self._move_start_time: float = 0
        self._move_duration: float = 0
        self._sync_task: asyncio.Task | None = None
        self.mount = mount

        # --- CONFIGURABLE GEOMETRY ---
        # These values would ideally be loaded from a config file or database.
        # They are based on the frontend defaults for now.
        self.geometry = DomeGeometry(
            latitude=-33.8559799094,
            longitude=151.20666584,
            elevation=46,
            dome_radius=2.5,
            mount_offset_ns=-0.13, # mountOffset.z from frontend
            mount_offset_ew=0.048,  # mountOffset.x from frontend
            mount_pier_height=1.2,  # pierHeight
            polar_axis_to_dec_axis=0.22, # polarAxisLengthMotorSideFull + polarAxisPositionHolderSide
            dec_axis_to_telescope=0.18 # decAxisPositionMain + decAxisLengthMotor
        )

    def _hms_to_hours(self, hms_str: str) -> float:
        """Converts HH:MM:SS.ss string to decimal hours."""
        if not hms_str: return 0.0
        parts = hms_str.split(':')
        if len(parts) != 3: return 0.0
        h, m, s = map(float, parts)
        return h + m / 60 + s / 3600


    async def connect(self):
        """Simulates connecting to the dome."""
        if not self._is_connected:
            print("Fake dome connected.")
            self._is_connected = True
            # Simulate a startup sync state
            self._is_syncing = False

    async def close(self):
        """Simulates disconnecting from the dome."""
        if self._is_connected:
            print("Fake dome disconnected.")
            # Clean up sync task on disconnect
            if self._sync_task:
                self._sync_task.cancel()
                self._sync_task = None
            self._is_connected = False

    def _update_position(self):
        """Private method to update the dome's position during a simulated move."""
        if not self._is_moving:
            return

        elapsed = time.time() - self._move_start_time
        if elapsed >= self._move_duration:
            self._azimuth = self._target_azimuth
            self._is_moving = False
        else:
            # Simple linear interpolation for azimuth
            fraction = elapsed / self._move_duration
            
            # Handle shortest path for rotation (e.g., 350 -> 10 degrees is a 20 degree move)
            delta = self._target_azimuth - self._start_azimuth
            if delta > 180:
                delta -= 360
            elif delta < -180:
                delta += 360
            
            new_az = (self._start_azimuth + delta * fraction) % 360
            self._azimuth = new_az

    async def get_status(self) -> tuple[float, bool]:
        """
        Gets the current status of the dome.

        Returns:
            A tuple containing the current azimuth (float) and moving status (bool).
        """
        if not self._is_connected:
            raise DomeError("Dome not connected")
        self._update_position()
        return self._azimuth, self._is_moving

    async def get_sync_status(self) -> bool:
        """Gets the dome's synchronization status."""
        if not self._is_connected:
            raise DomeError("Dome not connected")
        return self._is_syncing

    async def set_sync(self, sync_on: bool):
        """Enables or disables dome synchronization."""
        if not self._is_connected:
            raise DomeError("Dome not connected")
        self._is_syncing = sync_on
        if sync_on:
            if not self._sync_task or self._sync_task.done():
                self._sync_task = asyncio.create_task(self._sync_loop())
        else:
            if self._sync_task:
                self._sync_task.cancel()
                self._sync_task = None

    async def _sync_loop(self):
        """Periodically updates the dome azimuth to follow the telescope."""
        while self._is_syncing:
            try:
                # Get current telescope state
                ra_hours, dec_deg = await self.mount.get_mount_ra_dec(as_float=True)

                sidereal_str = await self.mount.get_sidereal_time()
                sidereal_hours = self._hms_to_hours(sidereal_str)
                
                pier_side = await self.mount.pier_side()

                # Calculate required dome azimuth
                target_az = self.geometry.calculate_dome_azimuth(
                    ra_hours=ra_hours,
                    dec_degrees=dec_deg,
                    sidereal_time_hours=sidereal_hours,
                    pier_side=pier_side
                )

                # Slew dome if not already moving and target is different
                if not self._is_moving and abs(target_az - self._target_azimuth) > 1.0:
                    print(f"Syncing dome to new azimuth: {target_az:.2f}")
                    await self.move_to_azimuth(target_az)

            except Exception as e:
                print(f"Error in dome sync loop: {e}")
            await asyncio.sleep(2) # Update every 2 seconds
    async def move_to_azimuth(self, target_az: float):
        """
        Simulates moving the dome to a target azimuth.

        Args:
            target_az: The target azimuth in degrees.
        """
        if not self._is_connected:
            raise DomeError("Dome not connected")
        if self._is_moving:
            raise DomeError("Dome is already moving")

        self._update_position() # Ensure current position is up-to-date
        self._target_azimuth = target_az
        self._start_azimuth = self._azimuth
        self._is_moving = True
        self._move_start_time = time.time()

        # Simulate slew time: 5 degrees per second
        slew_rate = 5.0 # deg/s
        self._move_duration = abs(self._target_azimuth - self._start_azimuth) / slew_rate

    async def stop_movement(self):
        """Stops any ongoing dome movement."""
        if not self._is_connected:
            raise DomeError("Dome not connected")

        # Update position to the current interpolated position before stopping
        self._update_position()
        if self._is_moving:
            self._is_moving = False