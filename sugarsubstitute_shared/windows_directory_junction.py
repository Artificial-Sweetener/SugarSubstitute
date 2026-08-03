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

"""Create Windows directory junctions without shelling out."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import sys

from sugarsubstitute_shared.windows_long_paths import logical_path, operational_path

_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FSCTL_SET_REPARSE_POINT = 0x000900A4
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


def create_windows_directory_junction(*, junction: Path, target: Path) -> None:
    """Create one directory junction to an existing absolute target."""

    if sys.platform != "win32":
        raise OSError("Windows directory junctions require Windows.")
    junction_path = operational_path(junction)
    target_path = operational_path(target)
    if not target_path.is_dir():
        raise FileNotFoundError(f"Junction target is not a directory: {target_path}")
    junction_path.mkdir(parents=False, exist_ok=False)
    try:
        _set_mount_point_reparse_data(junction_path, target_path)
    except Exception:
        junction_path.rmdir()
        raise


def _set_mount_point_reparse_data(junction: Path, target: Path) -> None:
    """Attach native mount-point reparse data to an empty directory."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    device_io_control = kernel32.DeviceIoControl
    device_io_control.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    device_io_control.restype = wintypes.BOOL

    handle = create_file(
        str(junction),
        _GENERIC_WRITE,
        0,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        reparse_data = _mount_point_reparse_data(target)
        input_buffer = ctypes.create_string_buffer(reparse_data)
        bytes_returned = wintypes.DWORD()
        succeeded = device_io_control(
            handle,
            _FSCTL_SET_REPARSE_POINT,
            ctypes.cast(input_buffer, wintypes.LPVOID),
            len(reparse_data),
            None,
            0,
            ctypes.byref(bytes_returned),
            None,
        )
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        close_handle(handle)


def _mount_point_reparse_data(target: Path) -> bytes:
    """Build one mount-point reparse buffer for an absolute target."""

    print_name = logical_path(target)
    if print_name.startswith("\\\\"):
        substitute_name = "\\??\\UNC\\" + print_name.removeprefix("\\\\")
    else:
        substitute_name = "\\??\\" + print_name
    substitute_bytes = substitute_name.encode("utf-16-le")
    print_bytes = print_name.encode("utf-16-le")
    path_buffer = substitute_bytes + b"\0\0" + print_bytes + b"\0\0"
    print_offset = len(substitute_bytes) + 2
    reparse_data_length = 8 + len(path_buffer)
    header = struct.pack(
        "<LHHHHHH",
        _IO_REPARSE_TAG_MOUNT_POINT,
        reparse_data_length,
        0,
        0,
        len(substitute_bytes),
        print_offset,
        len(print_bytes),
    )
    return header + path_buffer


__all__ = ["create_windows_directory_junction"]
