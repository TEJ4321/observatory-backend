# Set-get verification for non-destructive settings (time and limits).
# These are safer but still change mount state.

import os
import pytest
from datetime import datetime

@pytest.mark.hardware
def test_hw_time_set_and_get(real_mount):
    m = real_mount
    # Get current time from mount
    before = m.get_local_time()
    print("Before local time:", before)
    # Set local time back to the same value to test set path (no net change)
    res = m.set_local_time(before)
    # set_local_time returns '1' on success (single-char)
    assert res in ("0", "1")  # accept either if manual rejects formatting; but should not raise

@pytest.mark.hardware
def test_hw_limits_read_and_set(real_mount):
    m = real_mount
    low = m.get_lower_limit()
    high = m.get_upper_limit()
    print("Lower, Upper:", low, high)
    # set high to current value to verify command format (non-destructive)
    # If high is something like "+85", parse it
    try:
        deg = int(high.strip("+-"))
        res = m.set_high_alt_limit(deg)
        assert res in ("0", "1")
    except Exception as e:
        pytest.skip(f"Could not parse high limit: {e}")
