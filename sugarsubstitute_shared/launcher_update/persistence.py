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

"""Persist launcher update records atomically."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
from typing import Mapping, TextIO

from sugarsubstitute_shared.windows_long_paths import operational_path


_GENERIC_READ = 0x80000000
_DELETE = 0x00010000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_RENAME_INFO_EX = 22
_FILE_RENAME_REPLACE_IF_EXISTS = 0x00000001
_FILE_RENAME_POSIX_SEMANTICS = 0x00000002


class _FileRenameInfoEx(ctypes.Structure):
    """Match the variable-length Windows FILE_RENAME_INFO layout."""

    _fields_ = (
        ("flags", wintypes.DWORD),
        ("root_directory", wintypes.HANDLE),
        ("file_name_length", wintypes.DWORD),
        ("file_name", wintypes.WCHAR * 1),
    )


@contextmanager
def open_atomic_read(path: Path) -> Iterator[TextIO]:
    """Open one text snapshot without obstructing atomic replacement."""

    resolved_path = operational_path(path)
    if sys.platform != "win32":
        with resolved_path.open("r", encoding="utf-8") as source:
            yield source
        return

    source = _open_windows_atomic_read(resolved_path)
    try:
        yield source
    finally:
        source.close()


def _open_windows_atomic_read(path: Path) -> TextIO:
    """Open a Windows reader that shares the destination's delete access."""

    import msvcrt

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

    handle = create_file(
        os.fspath(path),
        _GENERIC_READ,
        _FILE_SHARE_READ | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = os.fspath(path)
        raise error
    try:
        descriptor = msvcrt.open_osfhandle(
            int(handle),
            os.O_RDONLY | os.O_BINARY,
        )
    except BaseException:
        close_handle(handle)
        raise
    return os.fdopen(descriptor, "r", encoding="utf-8")


def replace_atomic(source: Path, destination: Path) -> None:
    """Atomically replace one path, including over shared Windows readers."""

    source_path = operational_path(source)
    destination_path = operational_path(destination)
    if sys.platform != "win32":
        os.replace(source_path, destination_path)
        return
    _replace_windows_atomic(source_path, destination_path)


def _replace_windows_atomic(source: Path, destination: Path) -> None:
    """Use Windows POSIX rename semantics for an open shared destination."""

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
    set_file_information = kernel32.SetFileInformationByHandle
    set_file_information.argtypes = (
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    )
    set_file_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        os.fspath(source),
        _DELETE,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        error = ctypes.WinError(ctypes.get_last_error())
        error.filename = os.fspath(source)
        raise error
    try:
        encoded_destination = os.fspath(destination).encode("utf-16-le")
        buffer_size = (
            _FileRenameInfoEx.file_name.offset
            + len(encoded_destination)
            + ctypes.sizeof(wintypes.WCHAR)
        )
        buffer = ctypes.create_string_buffer(buffer_size)
        rename = _FileRenameInfoEx.from_buffer(buffer)
        rename.flags = _FILE_RENAME_REPLACE_IF_EXISTS | _FILE_RENAME_POSIX_SEMANTICS
        rename.root_directory = None
        rename.file_name_length = len(encoded_destination)
        ctypes.memmove(
            ctypes.addressof(buffer) + _FileRenameInfoEx.file_name.offset,
            encoded_destination,
            len(encoded_destination),
        )
        if not set_file_information(
            handle,
            _FILE_RENAME_INFO_EX,
            buffer,
            buffer_size,
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            error.filename = os.fspath(source)
            error.filename2 = os.fspath(destination)
            raise error
    finally:
        close_handle(handle)


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    """Write one JSON object through a same-directory temporary file."""

    path = operational_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    replace_atomic(temporary_path, path)


def read_json_object(path: Path) -> dict[str, object]:
    """Read one JSON object and reject other root values."""

    with open_atomic_read(path) as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


__all__ = [
    "open_atomic_read",
    "read_json_object",
    "replace_atomic",
    "write_json_atomic",
]
