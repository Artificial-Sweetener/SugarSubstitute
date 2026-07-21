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

"""Expose logical Windows paths through the extended-length filesystem namespace."""

from __future__ import annotations

import ntpath
import os
import errno
from pathlib import Path, WindowsPath
import sys
import tempfile
from typing import Self

_EXTENDED_PREFIX = "\\\\?\\"
_EXTENDED_UNC_PREFIX = "\\\\?\\UNC\\"
_UNC_PREFIX = "\\\\"
WINDOWS_LEGACY_PATH_LIMIT = 260
WINDOWS_PATH_COMPONENT_LIMIT = 255
_LONG_PATH_ERROR_MARKERS = (
    "filename too long",
    "file name too long",
    "path too long",
    "winerror 206",
    "error_filename_exced_range",
)


class ExternalLongPathCompatibilityError(RuntimeError):
    """Report a known long-path failure in an external component."""

    def __init__(
        self,
        *,
        component: str,
        path: os.PathLike[str] | str,
        detail: str,
    ) -> None:
        """Retain structured evidence for localized presentation."""

        self.component = component
        self.path = Path(logical_path(path))
        self.detail = detail
        super().__init__(
            f"{component} could not access the long Windows path "
            f"'{self.path}'. {detail}"
        )


class WindowsPathComponentTooLongError(ValueError):
    """Report one path component that exceeds the Windows filesystem limit."""

    def __init__(self, *, path: os.PathLike[str] | str, component: str) -> None:
        """Retain the logical path and offending component for presentation."""

        self.path = Path(logical_path(path))
        self.component = component
        super().__init__(
            "Windows limits each file or folder name to "
            f"{WINDOWS_PATH_COMPONENT_LIMIT} characters; '{component}' has "
            f"{len(component)} characters in '{self.path}'."
        )


class WindowsLongPath(WindowsPath):
    """Keep paths readable while giving Windows APIs an extended-length name."""

    def __fspath__(self) -> str:
        """Return the extended-length path consumed by filesystem APIs."""

        return extended_length_path(str(self))

    def resolve(self, strict: bool = False) -> Self:
        """Resolve the path without retaining the transport-only prefix."""

        resolved = super().resolve(strict=strict)
        return self.with_segments(logical_path(resolved))

    def absolute(self) -> Self:
        """Return an absolute path without retaining the transport-only prefix."""

        absolute = super().absolute()
        return self.with_segments(logical_path(absolute))


def operational_path(path: os.PathLike[str] | str) -> Path:
    """Return an absolute path that bypasses ``MAX_PATH`` on Windows."""

    logical = logical_path(path)
    candidate = Path(logical).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    normalized = (
        ntpath.normpath(str(candidate)) if sys.platform == "win32" else str(candidate)
    )
    if sys.platform != "win32":
        return Path(normalized)
    _validate_windows_components(normalized)
    return WindowsLongPath(normalized)


def subprocess_path(path: os.PathLike[str] | str) -> str:
    """Return a path argument safe for a Windows native child process."""

    operational = operational_path(path)
    return os.fspath(operational) if sys.platform == "win32" else str(operational)


def subprocess_working_directory(path: os.PathLike[str] | str) -> str:
    """Return a CreateProcess-compatible cwd, using a short neutral fallback."""

    operational = operational_path(path)
    if sys.platform != "win32" or not exceeds_windows_legacy_path_limit(operational):
        return str(operational)
    temp_directory = Path(tempfile.gettempdir()).resolve()
    if len(str(temp_directory)) < WINDOWS_LEGACY_PATH_LIMIT and temp_directory.is_dir():
        return str(temp_directory)
    windows_directory = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return str(windows_directory)


def qt_filesystem_path(path: os.PathLike[str] | str) -> str:
    """Return a path suitable for Qt file APIs on the active platform."""

    operational = operational_path(path)
    return os.fspath(operational) if sys.platform == "win32" else str(operational)


def extended_length_path(path: os.PathLike[str] | str) -> str:
    """Return one fully qualified Windows path in the extended namespace."""

    raw_path = logical_path(path)
    normalized = ntpath.normpath(raw_path)
    if not ntpath.isabs(normalized):
        raise ValueError("Extended-length Windows paths must be absolute.")
    if normalized.startswith(_UNC_PREFIX):
        return _EXTENDED_UNC_PREFIX + normalized.removeprefix(_UNC_PREFIX)
    return _EXTENDED_PREFIX + normalized


def logical_path(path: os.PathLike[str] | str) -> str:
    """Return a user-facing path without a Windows namespace prefix."""

    raw_path = str(path)
    if raw_path.startswith(_EXTENDED_UNC_PREFIX):
        return _UNC_PREFIX + raw_path.removeprefix(_EXTENDED_UNC_PREFIX)
    return raw_path.removeprefix(_EXTENDED_PREFIX)


def exceeds_windows_legacy_path_limit(path: os.PathLike[str] | str) -> bool:
    """Return whether a logical path exceeds the legacy Win32 path budget."""

    return (
        sys.platform == "win32" and len(logical_path(path)) >= WINDOWS_LEGACY_PATH_LIMIT
    )


def external_long_path_error(
    *,
    component: str,
    path: os.PathLike[str] | str,
    detail: BaseException | str,
) -> ExternalLongPathCompatibilityError | None:
    """Classify explicit external ``MAX_PATH`` failures for actionable handling."""

    if sys.platform != "win32" or not exceeds_windows_legacy_path_limit(path):
        return None
    detail_text = str(detail).strip() or type(detail).__name__
    winerror = getattr(detail, "winerror", None)
    error_number = getattr(detail, "errno", None)
    normalized = detail_text.casefold()
    if (
        winerror != 206
        and error_number != errno.ENAMETOOLONG
        and not any(marker in normalized for marker in _LONG_PATH_ERROR_MARKERS)
    ):
        return None
    return ExternalLongPathCompatibilityError(
        component=component,
        path=path,
        detail=detail_text,
    )


def _validate_windows_components(path: str) -> None:
    """Reject components that no Windows path namespace can represent."""

    drive, tail = ntpath.splitdrive(path)
    del drive
    for component in tail.split("\\"):
        if len(component) > WINDOWS_PATH_COMPONENT_LIMIT:
            raise WindowsPathComponentTooLongError(path=path, component=component)


__all__ = [
    "WINDOWS_LEGACY_PATH_LIMIT",
    "WINDOWS_PATH_COMPONENT_LIMIT",
    "ExternalLongPathCompatibilityError",
    "WindowsPathComponentTooLongError",
    "WindowsLongPath",
    "exceeds_windows_legacy_path_limit",
    "extended_length_path",
    "external_long_path_error",
    "logical_path",
    "operational_path",
    "qt_filesystem_path",
    "subprocess_path",
    "subprocess_working_directory",
]
