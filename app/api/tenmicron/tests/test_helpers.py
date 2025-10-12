import pytest
from tenmicron import TenMicronMount

def test_hours_to_hms_basic():
    assert TenMicronMount._hours_to_hms(0.0) == "00:00:00.00"
    assert TenMicronMount._hours_to_hms(23.9997222222).startswith("23:59:59")

def test_hours_to_hms_roundtrip():
    for val in [0.0, 0.5, 12.3456, 23.9999]:
        hms = TenMicronMount._hours_to_hms(val)
        back = TenMicronMount._hms_to_hours(hms)
        assert abs(back - (val % 24)) < 1e-6

def test_degrees_to_dms_roundtrip_signed():
    for deg in [-89.9999, -45.5, 0.0, 45.1234, 179.9999]:
        dms = TenMicronMount._degrees_to_dms(deg, signed=True)
        back = TenMicronMount._dms_to_degrees(dms)
        assert abs(back - deg) < 1e-6

def test_degrees_to_dms_unsigned():
    dms = TenMicronMount._degrees_to_dms(123.456, signed=False)
    assert dms.startswith("123:")
    assert abs(TenMicronMount._dms_to_degrees(dms) - 123.456) < 1e-6

def test_invalid_hms_to_hours_raises():
    with pytest.raises(Exception):
        TenMicronMount._hms_to_hours("not:a:time")

def test_invalid_dms_to_degrees_raises():
    with pytest.raises(Exception):
        TenMicronMount._dms_to_degrees("not:dms")
