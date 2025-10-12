# Edge-case coverage:
# invalid formatting, invalid responses, degree symbol replacement, merged single-char replies.

import pytest
from tenmicron import TenMicronMount, MountError

def test_lx200_degree_symbol_conversion(make_mount_with_responses):
    # 0xDF represented in latin-1 decode often becomes ß; ensure replacement to °
    # Simulate raw bytes containing 0xDF (223), but in python bytes we can include it.
    m = make_mount_with_responses([bytes([49, 223, 35])])  # '1' + 0xDF + '#'
    result = m.send_command(":GR", terminated=True)
    # Expect the 0xDF to be converted to degree sign and stripped '#'
    assert "°" in result or result == "1°"

def test_merged_single_char_responses(make_mount_with_responses):
    # simulate "1#0#" returned for two successive single-char replies packed together
    m = make_mount_with_responses([b"1#0#"])
    out = m.send_command(":Sr12:00:00", terminated=True)  # although single-char expected, simulate terminated
    assert out == "1"
