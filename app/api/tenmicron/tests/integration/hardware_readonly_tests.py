# Safe read-only checks (status, firmware, positions).

import os
import pytest

@pytest.mark.hardware
def test_hw_status_and_info(real_mount):
    m = real_mount
    code = m.get_status_code()
    assert isinstance(code, str)
    info = m.product_name()
    assert isinstance(info, str)
    # read RA/Dec and Alt/Az
    ra = m.get_mount_ra()
    dec = m.get_mount_dec()
    alt = m.get_mount_alt()
    az = m.get_mount_az()
    print("RA, Dec, Alt, Az:", ra, dec, alt, az)
    assert ":" in ra and ":" in dec

