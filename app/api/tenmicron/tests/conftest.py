# Fixtures for mocked sockets and an optional real-mount fixture
# (enabled only when --run-hardware env var is set).
# It also provides a make_mount_with_responses() helper.

import time
import os
import socket
import pytest
from types import SimpleNamespace
from tenmicron import TenMicronMount, MountError

class FakeSocket:
    """
    Fake socket that returns a list of byte responses on successive recv() calls.
    Tracks data sent via sendall().
    """
    def __init__(self, responses=None):
        self._responses = list(responses) if responses else []
        self.sent = []
        self._timeout = 1.0
        self.closed = False

    def settimeout(self, t):
        self._timeout = t

    def sendall(self, data: bytes):
        self.sent.append(data)

    def recv(self, bufsize: int):
        # Simulate socket.timeout if no responses left
        if not self._responses:
            raise socket.timeout("No more data")
            # time.sleep(self._timeout)
        return self._responses.pop(0)

    def close(self):
        self.closed = True

@pytest.fixture
def fake_socket():
    """Yield a fresh FakeSocket for test to configure responses."""
    return FakeSocket

@pytest.fixture
def make_mount_with_responses(fake_socket):
    """Factory fixture: returns TenMicronMount instance with fake socket preloaded."""
    def _make(responses):
        m = TenMicronMount("127.0.0.1")
        m.sock = fake_socket(responses)
        return m
    return _make

# Real hardware fixture (disabled unless environment variable is set)
@pytest.fixture(scope="session")
def real_mount():
    """
    Provide a real TenMicronMount connected to hardware if environment variable RUN_HARDWARE_TESTS=1.
    Otherwise skip tests marked hardware.
    """
    run_hw = os.getenv("RUN_HARDWARE_TESTS", "0") == "1"
    if not run_hw:
        pytest.skip("Hardware tests disabled. Set RUN_HARDWARE_TESTS=1 to enable.", allow_module_level=True)

    # Provide simple mount instance - configure host/port through env vars
    host = os.getenv("TENMICRON_HOST", "192.168.1.10")
    port = int(os.getenv("TENMICRON_PORT", "3492"))
    m = TenMicronMount(host, port=port, timeout=5.0)
    try:
        m.connect()
    except Exception as e:
        pytest.skip(f"Cannot connect to mount ({e}) - skipping hardware tests")
    yield m
    try:
        m.close()
    except Exception:
        pass
