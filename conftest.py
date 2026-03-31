"""Root conftest — Windows event loop and socket compatibility."""
from __future__ import annotations

import socket
import sys


def pytest_configure(config):
    """Configure pytest for Windows compatibility.

    On Windows, asyncio.SelectorEventLoop uses socket.socketpair() internally
    which creates AF_INET loopback sockets. pytest-socket blocks these by default.
    We patch disable_socket to allow AF_INET localhost pairs on Windows.
    """
    if sys.platform != "win32":
        return

    try:
        import pytest_socket

        _original_disable = pytest_socket.disable_socket

        def _windows_disable_socket(allow_unix_socket=False):
            """Wrap disable_socket to also allow localhost socketpairs on Windows."""
            import socket as _socket

            _true_socket = _socket.socket

            class WindowsGuardedSocket(_true_socket):
                """Allow AF_INET localhost pairs needed by asyncio on Windows."""

                def __new__(cls, family=-1, type=-1, proto=-1, fileno=None):
                    # Allow AF_UNIX if requested
                    if (
                        family != -1
                        and hasattr(_socket, "AF_UNIX")
                        and family == _socket.AF_UNIX
                        and allow_unix_socket
                    ):
                        return _true_socket.__new__(cls, family, type, proto, fileno)
                    # Allow AF_INET loopback — needed by asyncio SelectorEventLoop
                    # for internal self-pipe on Windows
                    if family == _socket.AF_INET or family == -1:
                        return _true_socket.__new__(cls, family, type, proto, fileno)
                    raise pytest_socket.SocketBlockedError()

            _socket.socket = WindowsGuardedSocket

        pytest_socket.disable_socket = _windows_disable_socket

    except ImportError:
        pass
