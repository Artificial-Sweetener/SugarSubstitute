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

"""Bind Windows handoff verification and waiting to one kernel process handle."""

from __future__ import annotations

import math
from typing import Protocol

from sugarsubstitute_shared.windows_process_handle_api import NativeProcessHandleApi

from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
)


class ProcessWaitApi(Protocol):
    """Expose handle-based Windows process operations for deterministic race tests."""

    def open(self, pid: int) -> int | None:
        """Retain a process object, or report that its PID no longer exists."""

    def creation_time(self, handle: int) -> float:
        """Read kernel creation time from the retained object."""

    def wait(self, handle: int, milliseconds: int) -> bool:
        """Return whether the retained process object reached its terminal state."""

    def close(self, handle: int) -> None:
        """Release this caller's retained process reference."""


def wait_for_windows_process_exit(
    identity: ProcessIdentity,
    *,
    timeout_seconds: float,
    api: ProcessWaitApi | None = None,
) -> None:
    """Check identity and await exit without reopening a potentially reused PID."""
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise ValueError("Process wait timeout must be finite and nonnegative.")
    native = api or NativeProcessHandleApi()
    try:
        handle = native.open(identity.pid)
        if handle is None:
            return
        try:
            if abs(native.creation_time(handle) - identity.created_at) > 0.000_001:
                return
            milliseconds = min(math.ceil(timeout_seconds * 1000), 0xFFFFFFFE)
            if not native.wait(handle, milliseconds):
                raise ProcessIdentityError(
                    f"Timed out waiting for process: {identity.pid}"
                )
        finally:
            native.close(handle)
    except OSError as error:
        raise ProcessIdentityError(
            f"Could not wait for process: {identity.pid}"
        ) from error
