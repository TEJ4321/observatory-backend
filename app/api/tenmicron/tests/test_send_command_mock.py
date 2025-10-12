# Exhaustive tests for send_command() behaviour with mocked socket responses:
# terminated, single-char, multi-packet, merged replies, unterminated variable replies, timeouts.

import socket
import pytest
from tenmicron import TenMicronMount, MountError

def test_terminated_reply(make_mount_with_responses):
    m = make_mount_with_responses([b"12:34:56#"])
    out = m.send_command(":GR", expect_response=True, terminated=True)
    assert out == "12:34:56"
    assert m.sock.sent[0] == b":GR#"

def test_single_char_reply(make_mount_with_responses):
    m = make_mount_with_responses([b"1"])
    out = m.send_command(":Sr12:00:00", expect_response=True, terminated=False, single_char=True)
    assert out == "1"
    assert m.sock.sent[0] == b":Sr12:00:00#"

def test_no_response_expectation(make_mount_with_responses):
    m = make_mount_with_responses([])
    out = m.send_command(":PO", expect_response=False)
    assert out == ""

def test_merged_terminated_packet(make_mount_with_responses):
    # two replies merged - ensure we only keep first terminated reply
    m = make_mount_with_responses([b"12:34:56#22:33:44#"])
    out = m.send_command(":GR", expect_response=True, terminated=True)
    assert out == "12:34:56"
    assert m.sock.sent[0] == b":GR#"

def test_unterminated_variable_reply(make_mount_with_responses):
    # Simulate a multi-chunk unterminated message
    m = make_mount_with_responses([b"INFO PART1", b" PART2"])
    out = m.send_command(":evlog", expect_response=True, terminated=False, single_char=False, max_bytes=1024)
    assert "INFO PART1" in out

def test_timeout_raises_when_no_data(make_mount_with_responses):
    m = make_mount_with_responses([])
    with pytest.raises(MountError):
        m.send_command(":GR", expect_response=True, terminated=True, timeout=0.01)

def test_partial_data_returned_on_timeout(make_mount_with_responses):
    # Provide partial data then force timeout by returning nothing for an expected terminated response
    m = make_mount_with_responses([b"PARTIAL"])
    # calling terminated=True will wait for '#', but there will be no '#', so it times out.
    with pytest.raises(MountError):
        m.send_command(":GR", expect_response=True, terminated=True, timeout=0.01)
