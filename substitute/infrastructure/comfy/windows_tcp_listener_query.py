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

"""Resolve Windows TCP listener ownership through the native IP Helper API."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import socket
from typing import Final


_AF_INET: Final = 2
_AF_INET6: Final = 23
_ERROR_INSUFFICIENT_BUFFER: Final = 122
_NO_ERROR: Final = 0
_TCP_TABLE_OWNER_PID_LISTENER: Final = 3


class _MibTcpRowOwnerPid(ctypes.Structure):
    """Mirror one IPv4 ``MIB_TCPROW_OWNER_PID`` entry."""

    _fields_ = [
        ("state", wintypes.DWORD),
        ("local_address", wintypes.DWORD),
        ("local_port", wintypes.DWORD),
        ("remote_address", wintypes.DWORD),
        ("remote_port", wintypes.DWORD),
        ("owning_pid", wintypes.DWORD),
    ]


class _MibTcp6RowOwnerPid(ctypes.Structure):
    """Mirror one IPv6 ``MIB_TCP6ROW_OWNER_PID`` entry."""

    _fields_ = [
        ("local_address", ctypes.c_ubyte * 16),
        ("local_scope_id", wintypes.DWORD),
        ("local_port", wintypes.DWORD),
        ("remote_address", ctypes.c_ubyte * 16),
        ("remote_scope_id", wintypes.DWORD),
        ("remote_port", wintypes.DWORD),
        ("state", wintypes.DWORD),
        ("owning_pid", wintypes.DWORD),
    ]


def get_windows_tcp_listener_pid(host: str, port: int) -> int | None:
    """Return the native owner of one loopback listener when present."""

    if host == "127.0.0.1":
        return _query_ipv4_listener(host=host, port=port)
    if host == "::1":
        return _query_ipv6_listener(host=host, port=port)
    if host == "localhost":
        ipv4_pid = _query_ipv4_listener(host="127.0.0.1", port=port)
        return ipv4_pid or _query_ipv6_listener(host="::1", port=port)
    raise ValueError(f"Windows listener ownership requires a loopback host: {host}")


def _query_ipv4_listener(*, host: str, port: int) -> int | None:
    """Find one IPv4 listener owner in the native table."""

    buffer = _load_listener_table(address_family=_AF_INET)
    for row in _table_rows(buffer, _MibTcpRowOwnerPid):
        local_address = socket.inet_ntoa(
            int(row.local_address).to_bytes(4, byteorder="little")
        )
        if _decode_network_port(row.local_port) == port and local_address in {
            host,
            "0.0.0.0",
        }:
            return int(row.owning_pid)
    return None


def _query_ipv6_listener(*, host: str, port: int) -> int | None:
    """Find one IPv6 listener owner in the native table."""

    buffer = _load_listener_table(address_family=_AF_INET6)
    for row in _table_rows(buffer, _MibTcp6RowOwnerPid):
        local_address = socket.inet_ntop(socket.AF_INET6, bytes(row.local_address))
        if _decode_network_port(row.local_port) == port and local_address in {
            host,
            "::",
        }:
            return int(row.owning_pid)
    return None


def _load_listener_table(*, address_family: int) -> ctypes.Array[ctypes.c_char]:
    """Return one complete native owner-PID listener table."""

    ip_helper = ctypes.WinDLL("iphlpapi.dll", use_last_error=True)
    get_table = ip_helper.GetExtendedTcpTable
    get_table.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.BOOL,
        wintypes.ULONG,
        ctypes.c_int,
        wintypes.ULONG,
    ]
    get_table.restype = wintypes.DWORD
    size = wintypes.DWORD()
    status = int(
        get_table(
            None,
            ctypes.byref(size),
            False,
            address_family,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    )
    if status not in {_NO_ERROR, _ERROR_INSUFFICIENT_BUFFER}:
        raise ctypes.WinError(status)
    buffer = ctypes.create_string_buffer(max(size.value, ctypes.sizeof(wintypes.DWORD)))
    status = int(
        get_table(
            buffer,
            ctypes.byref(size),
            False,
            address_family,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    )
    if status != _NO_ERROR:
        raise ctypes.WinError(status)
    return buffer


def _table_rows[RowT: ctypes.Structure](
    buffer: ctypes.Array[ctypes.c_char], row_type: type[RowT]
) -> tuple[RowT, ...]:
    """Parse validated rows from a variable-length native listener table."""

    count_size = ctypes.sizeof(wintypes.DWORD)
    row_size = ctypes.sizeof(row_type)
    row_count = int(wintypes.DWORD.from_buffer_copy(buffer.raw[:count_size]).value)
    available_rows = (len(buffer) - count_size) // row_size
    if row_count > available_rows:
        raise OSError("Windows returned a truncated TCP listener table.")
    return tuple(
        row_type.from_buffer_copy(buffer.raw, count_size + index * row_size)
        for index in range(row_count)
    )


def _decode_network_port(encoded_port: int) -> int:
    """Decode the low-order network-byte-order port from an IP Helper row."""

    return int(socket.ntohs(int(encoded_port) & 0xFFFF))


__all__ = ["get_windows_tcp_listener_pid"]
