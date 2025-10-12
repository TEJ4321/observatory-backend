# Comprehensive high-level method tests. For each public method, we assert:
# - correct socket command bytes were sent,
# - the method returns expected parsed output,
# - numeric inputs are formatted correctly.

from tenmicron import TenMicronMount

def test_get_status_mapping(make_mount_with_responses):
    m = make_mount_with_responses([b"0#", b"0#"])
    assert m.get_status_code() == "0"
    assert m.get_status() == "Tracking"

def test_set_target_ra_float_sends_formatted_ra(make_mount_with_responses):
    m = make_mount_with_responses([b"1"])
    res = m.set_target_ra(12.5)
    assert res == "1"
    sent = m.sock.sent[0].decode()
    assert sent.startswith(":Sr12:30:00")

def test_set_target_dec_float(make_mount_with_responses):
    m = make_mount_with_responses([b"1"])
    res = m.set_target_dec(-22.5)
    assert res == "1"
    sent = m.sock.sent[0].decode()
    assert sent.startswith(":Sd-22:30:00")

def test_get_mount_ra_dec_as_float(make_mount_with_responses):
    # RA and Dec replies terminated
    m = make_mount_with_responses([b"12:30:15.50#", b"+22:30:00.00#"])
    ra, dec = m.get_mount_ra_dec(as_float=True)
    assert abs(ra - 12.5043055555) < 1e-6  # approximate
    assert abs(dec - 22.5) < 1e-6

def test_set_target_ra_dec_returns_dict(make_mount_with_responses):
    m = make_mount_with_responses([b"1", b"1"])
    results = m.set_target_ra_dec(12.0, 45.0)
    assert results == {"ra": "1", "dec": "1"}
    # verify both commands were sent
    assert len(m.sock.sent) == 2

def test_get_ip_info_parsed(make_mount_with_responses):
    m = make_mount_with_responses([b"192.168.1.10,255.255.255.0,192.168.1.1,D#"])
    ip, subnet, gateway, dhcp = m.get_ip_info()
    assert ip == "192.168.1.10"
    assert subnet == "255.255.255.0"
    assert gateway == "192.168.1.1"
    assert dhcp is True
