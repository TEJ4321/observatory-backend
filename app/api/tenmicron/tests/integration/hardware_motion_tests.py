# Dangerous motion tests.
# Disabled unless both RUN_HARDWARE_TESTS=1 and RUN_MOTION_TESTS=1 are set.
# They will ask for user confirmation before moving.

import os
import pytest

@pytest.mark.hardware
@pytest.mark.motion
def test_hw_slew_set_and_verify(real_mount):
    m = real_mount
    # Safety check environment variable
    if os.getenv("RUN_MOTION_TESTS", "0") != "1":
        pytest.skip("Motion tests disabled. Set RUN_MOTION_TESTS=1 to enable.")

    # Ask user to confirm in console
    print("About to perform a small safe slew to verify motion. Ensure area is clear and press ENTER to continue.")
    input("Press ENTER to proceed or Ctrl+C to abort...")

    # Choose a safe test target: current RA/Dec offset by small amount
    ra_s, dec_s = m.get_mount_ra_dec()
    ra_h = m._hms_to_hours(ra_s)
    dec_deg = m._dms_to_degrees(dec_s)
    # Move RA by +0.01h (~0.15°) and Dec by +0.1°
    new_ra = (ra_h + 0.01) % 24
    new_dec = dec_deg + 0.1
    print("Slewing to small test target:", new_ra, new_dec)
    m.set_target_ra_dec(new_ra, new_dec)
    slew_resp = m.slew_to_target_equatorial(None)
    print("Slew response:", slew_resp)

    # Wait until motion completes (poll status)
    import time
    for _ in range(60):
        st = m.get_status_code()
        if st not in ("6", "2", "4"):  # not slewing states (approx)
            break
        time.sleep(1)
    # read back current position and assert close to target
    current_ra, current_dec = m.get_mount_ra_dec(as_float=True)
    assert abs(current_ra - new_ra) < 0.01  # coarse check
    assert abs(current_dec - new_dec) < 0.5
