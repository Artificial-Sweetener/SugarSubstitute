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

"""Load the tiny native bridge that registers this process with Crashpad."""

from __future__ import annotations

from collections.abc import Callable
import ctypes
from pathlib import Path
from typing import Protocol, cast

from sugarsubstitute_shared.crash_reporting.protocol import CrashRunContext


class CrashpadInitializationError(RuntimeError):
    """Report a process that could not establish native crash capture."""


class _CrashpadStartFunction(Protocol):
    """Describe the exported Crashpad bridge function."""

    argtypes: list[object]
    restype: object

    def __call__(
        self,
        handler_path: bytes,
        database_path: bytes,
        metrics_path: bytes,
        attachment_path: bytes,
        application_version: bytes,
        run_id: bytes,
    ) -> int:
        """Start Crashpad and return one on success."""


class CrashpadNativeClient:
    """Retain the loaded native bridge for the complete process lifetime."""

    def __init__(
        self,
        *,
        library_loader: Callable[[str], ctypes.CDLL] = ctypes.CDLL,
    ) -> None:
        """Store the dynamic-library boundary for deterministic tests."""

        self._library_loader = library_loader
        self._library: ctypes.CDLL | None = None

    def start(
        self,
        *,
        context: CrashRunContext,
        application_version: str,
        attachment_path: Path,
    ) -> None:
        """Register this process with the supervisor-provided Crashpad handler."""

        handler = context.crashpad_handler
        client_library = context.crashpad_client_library
        if handler is None or client_library is None:
            raise CrashpadInitializationError(
                "Crashpad native paths are missing from the run contract."
            )
        if not handler.is_file() or not client_library.is_file():
            raise CrashpadInitializationError(
                "The packaged Crashpad native runtime is incomplete."
            )
        context.crashpad_database.mkdir(parents=True, exist_ok=True)
        metrics_path = context.crashpad_database / "metrics"
        metrics_path.mkdir(parents=True, exist_ok=True)
        try:
            library = self._library_loader(str(client_library))
            start_function = cast(
                _CrashpadStartFunction,
                getattr(library, "SugarSubstituteCrashpadStart"),
            )
            start_function.argtypes = [ctypes.c_char_p] * 6
            start_function.restype = ctypes.c_int
            started = start_function(
                _utf8(handler),
                _utf8(context.crashpad_database),
                _utf8(metrics_path),
                _utf8(attachment_path),
                application_version.encode("utf-8"),
                context.run_id.encode("utf-8"),
            )
        except (AttributeError, OSError) as error:
            raise CrashpadInitializationError(
                "The Crashpad native client could not be loaded."
            ) from error
        if started != 1:
            raise CrashpadInitializationError(
                "Crashpad rejected native process registration."
            )
        self._library = library


def _utf8(path: Path) -> bytes:
    """Encode one cross-platform native path for the bridge ABI."""

    return str(path).encode("utf-8")


__all__ = ["CrashpadInitializationError", "CrashpadNativeClient"]
