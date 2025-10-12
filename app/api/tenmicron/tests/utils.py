# Helper functions used by tests, e.g. to check message formatting.

from tenmicron import TenMicronMount

def sent_command_of(fake_mount):
    """Return the last command string (decoded) sent to fake socket."""
    # fake_mount.sock.sent is list of bytes; return last one decoded and stripped
    return fake_mount.sock.sent[-1].decode("ascii") if fake_mount.sock.sent else None

def assert_hms_close(hms_str, expected_hours, tol_seconds=0.02):
    """Assert an HH:MM:SS.SS string represents expected_hours within tolerance."""
    hours = TenMicronMount._hms_to_hours(hms_str)
    assert abs(hours - expected_hours) < tol_seconds/3600.0
