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

"""Capture and wait for process identities without PID-reuse races."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import sys

import psutil  # type: ignore[import-untyped]

_LOGGER = logging.getLogger(__name__)


class ProcessIdentityError(RuntimeError):
    """Report an inaccessible, reused, or unresponsive process identity."""


@dataclass(frozen=True, slots=True)
class ProcessIdentity:
    """Identify one OS process by both PID and kernel creation time."""

    pid: int
    created_at: float

    def __post_init__(self) -> None:
        """Require a positive finite kernel timestamp before comparing incarnations."""
        if not math.isfinite(self.created_at) or self.created_at <= 0:
            raise ValueError("Process creation time must be positive and finite.")


def capture_process_identity(pid: int) -> ProcessIdentity:
    """Capture the kernel-backed identity of one live process."""

    if pid <= 0:
        raise ProcessIdentityError("Process PID must be positive.")
    try:
        process = psutil.Process(pid)
        return ProcessIdentity(pid=pid, created_at=float(process.create_time()))
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as error:
        raise ProcessIdentityError(f"Could not identify process: {pid}") from error


def capture_expected_process_identity(
    pid: int, *, expected_executable: Path
) -> ProcessIdentity | None:
    """Bind a legacy PID only when its live executable is the expected launcher.

    A missing process has already satisfied the handoff wait. An inaccessible or
    different process is never accepted because a persisted PID may have been
    reused between the legacy scheduler and this updater process.
    """

    if pid <= 0:
        raise ProcessIdentityError("Process PID must be positive.")
    try:
        process = psutil.Process(pid)
        created_at = float(process.create_time())
        executable = Path(process.exe()).expanduser().resolve()
    except psutil.NoSuchProcess:
        return None
    except (psutil.AccessDenied, OSError) as error:
        raise ProcessIdentityError(f"Could not identify process: {pid}") from error
    expected = expected_executable.expanduser().resolve()
    if os.path.normcase(str(executable)) != os.path.normcase(str(expected)):
        raise ProcessIdentityError(
            f"Legacy launcher PID belongs to an unexpected executable: {executable}"
        )
    return ProcessIdentity(pid=pid, created_at=created_at)


def wait_for_process_exit(
    identity: ProcessIdentity,
    *,
    timeout_seconds: float = 120.0,
) -> None:
    """Wait for the captured incarnation; a replacement PID means it has exited."""

    if sys.platform == "win32":
        from sugarsubstitute_shared.windows_process_wait import (
            wait_for_windows_process_exit,
        )

        wait_for_windows_process_exit(identity, timeout_seconds=timeout_seconds)
        return
    try:
        process = psutil.Process(identity.pid)
        observed_creation = float(process.create_time())
    except psutil.NoSuchProcess:
        return
    except (psutil.AccessDenied, OSError) as error:
        raise ProcessIdentityError(
            f"Could not inspect process: {identity.pid}"
        ) from error
    if abs(observed_creation - identity.created_at) > 0.000_001:
        _LOGGER.info(
            "Outgoing process incarnation has exited; leaving reused PID untouched",
            extra={"outgoing_process_id": identity.pid},
        )
        return
    try:
        process.wait(timeout=timeout_seconds)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired as error:
        raise ProcessIdentityError(
            f"Timed out waiting for process: {identity.pid}"
        ) from error


__all__ = [
    "ProcessIdentity",
    "ProcessIdentityError",
    "capture_process_identity",
    "capture_expected_process_identity",
    "wait_for_process_exit",
]
