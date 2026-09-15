#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Own Windows application-instance election through one secured named pipe."""

from __future__ import annotations

import ctypes
from multiprocessing.connection import Client, Connection
import threading
from typing import cast

from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceConnection,
    ApplicationInstanceEndpoint,
)

from sugarsubstitute_shared.windows_process_security import process_user_sid

_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_PIPE_BUFFER_BYTES = 65536
_PIPE_CONNECT_WAIT_MILLISECONDS = 100


class WindowsNamedPipeConnection:
    """Frame messages over one local Windows named-pipe connection."""

    def __init__(self, connection: Connection, *, peer_is_server: bool) -> None:
        """Retain one pipe and record which peer process must be inspected."""

        self._connection = connection
        self._peer_is_server = peer_is_server

    def send_frame(self, payload: bytes) -> None:
        """Send one native message-mode pipe frame."""

        self._connection.send_bytes(payload)

    def receive_frame(
        self,
        maximum_size: int,
        *,
        timeout_seconds: float | None = None,
    ) -> bytes:
        """Receive one bounded native frame within an optional deadline."""

        try:
            if timeout_seconds is not None and not self._connection.poll(
                timeout_seconds
            ):
                raise TimeoutError("Application instance response timed out.")
            return self._connection.recv_bytes(maximum_size)
        except (EOFError, TypeError) as error:
            raise OSError("Application instance named pipe disconnected.") from error

    def close(self) -> None:
        """Close the named-pipe handle."""

        self._connection.close()

    def peer_is_current_user(self) -> bool:
        """Verify the pipe peer through its kernel process token."""

        handle = self._connection.fileno()
        peer_process_id = _named_pipe_peer_process_id(
            handle,
            peer_is_server=self._peer_is_server,
        )
        return process_user_sid(peer_process_id) == process_user_sid(None)

    def peer_process_id(self) -> int | None:
        """Return the peer process identifier reported by the named pipe kernel."""

        return _named_pipe_peer_process_id(
            self._connection.fileno(),
            peer_is_server=self._peer_is_server,
        )


class WindowsNamedPipeListener:
    """Hold the first and therefore authoritative named-pipe instance."""

    def __init__(self, endpoint: ApplicationInstanceEndpoint) -> None:
        """Atomically create a local-only first pipe with the token default DACL."""

        self._address = endpoint.address
        self._lock = threading.Lock()
        self._closed = False
        self._pending_handles = [self._new_handle(first=True)]
        self._active_accept_connection: Connection | None = None

    def accept(self) -> ApplicationInstanceConnection:
        """Accept one same-user client and reject every other token owner."""

        connection = self._accept_connection()
        wrapped = WindowsNamedPipeConnection(connection, peer_is_server=False)
        if not wrapped.peer_is_current_user():
            wrapped.close()
            raise PermissionError("Application instance peer belongs to another user.")
        return wrapped

    def close(self) -> None:
        """Close every pending named-pipe instance and release election ownership."""

        from _winapi import CloseHandle

        with self._lock:
            if self._closed:
                return
            self._closed = True
            handles = [*self._pending_handles]
            self._pending_handles.clear()
            accept_connection = self._active_accept_connection
            self._active_accept_connection = None
        if accept_connection is not None:
            accept_connection.close()
        for handle in handles:
            try:
                CloseHandle(handle)
            except OSError:
                pass

    def _new_handle(self, *, first: bool = False) -> int:
        """Create one local-only pipe instance, optionally requiring first owner."""

        import _winapi

        access_flags = _winapi.PIPE_ACCESS_DUPLEX | _winapi.FILE_FLAG_OVERLAPPED
        if first:
            access_flags |= _winapi.FILE_FLAG_FIRST_PIPE_INSTANCE
        pipe_mode = (
            _winapi.PIPE_TYPE_MESSAGE
            | _winapi.PIPE_READMODE_MESSAGE
            | _winapi.PIPE_WAIT
            | _PIPE_REJECT_REMOTE_CLIENTS
        )
        return int(
            _winapi.CreateNamedPipe(
                self._address,
                access_flags,
                pipe_mode,
                _winapi.PIPE_UNLIMITED_INSTANCES,
                _PIPE_BUFFER_BYTES,
                _PIPE_BUFFER_BYTES,
                _winapi.NMPWAIT_WAIT_FOREVER,
                _winapi.NULL,
            )
        )

    def _accept_connection(self) -> Connection:
        """Accept one client while keeping a replacement pipe instance ready."""

        import _winapi
        from multiprocessing.connection import PipeConnection

        with self._lock:
            if self._closed:
                raise OSError("Application instance named-pipe listener is closed.")
            self._pending_handles.append(self._new_handle())
            handle = self._pending_handles.pop(0)
            connection = cast(Connection, PipeConnection(handle))
            self._active_accept_connection = connection
        try:
            try:
                overlapped = _winapi.ConnectNamedPipe(handle, overlapped=True)
            except OSError as error:
                if error.winerror != _winapi.ERROR_NO_DATA:
                    raise
            else:
                try:
                    _winapi.WaitForMultipleObjects(
                        [overlapped.event],
                        False,
                        _winapi.INFINITE,
                    )
                except BaseException:
                    overlapped.cancel()
                    raise
                finally:
                    _result, native_error = overlapped.GetOverlappedResult(True)
                    if native_error:
                        raise OSError(native_error, "Named-pipe connection failed.")
            return connection
        except BaseException:
            connection.close()
            raise
        finally:
            with self._lock:
                if self._active_accept_connection is connection:
                    self._active_accept_connection = None


def connect_windows_named_pipe(
    endpoint: ApplicationInstanceEndpoint,
) -> WindowsNamedPipeConnection:
    """Connect to and authenticate the elected Windows supervisor."""

    import _winapi

    _winapi.WaitNamedPipe(endpoint.address, _PIPE_CONNECT_WAIT_MILLISECONDS)
    connection = cast(Connection, Client(endpoint.address, family="AF_PIPE"))
    wrapped = WindowsNamedPipeConnection(connection, peer_is_server=True)
    if not wrapped.peer_is_current_user():
        wrapped.close()
        raise PermissionError("Application instance owner belongs to another user.")
    return wrapped


def _named_pipe_peer_process_id(handle: int, *, peer_is_server: bool) -> int:
    """Return the process ID supplied by the named-pipe kernel object."""

    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function_name = (
        "GetNamedPipeServerProcessId"
        if peer_is_server
        else "GetNamedPipeClientProcessId"
    )
    query = getattr(kernel32, function_name)
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    query.restype = wintypes.BOOL
    process_id = wintypes.ULONG()
    if not query(wintypes.HANDLE(handle), ctypes.byref(process_id)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(process_id.value)


__all__ = [
    "WindowsNamedPipeConnection",
    "WindowsNamedPipeListener",
    "connect_windows_named_pipe",
]
