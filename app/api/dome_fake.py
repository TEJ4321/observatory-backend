import asyncio
import time

class DomeError(Exception):
    """Custom exception for Dome communication errors."""
    pass

class DomeFake:
    """
    A fake class that mimics a dome controller for testing purposes.
    It manages its own state for azimuth, movement, and synchronization.
    """
    def __init__(self):
        self._is_connected: bool = False
        self._azimuth: float = 180.0
        self._is_moving: bool = False
        self._is_syncing: bool = True
        self._target_azimuth: float = 180.0
        self._start_azimuth: float = 180.0
        self._move_start_time: float = 0
        self._move_duration: float = 0

    async def connect(self):
        """Simulates connecting to the dome."""
        if not self._is_connected:
            print("Fake dome connected.")
            self._is_connected = True
            # Simulate a startup sync state
            self._is_syncing = True

    async def close(self):
        """Simulates disconnecting from the dome."""
        if self._is_connected:
            print("Fake dome disconnected.")
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