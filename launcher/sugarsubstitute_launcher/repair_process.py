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

import psutil  # type: ignore[import-untyped]


class RepairProcessError(RuntimeError):
    """Report an inaccessible, reused, or unresponsive handoff process."""


@dataclass(frozen=True, slots=True)
class RepairProcessIdentity:
    """Identify one OS process by both PID and kernel creation time."""

    pid: int
    created_at: float


def capture_process_identity(pid: int) -> RepairProcessIdentity:
    """Capture the kernel-backed identity of one live process."""

    if pid <= 0:
        raise RepairProcessError("Repair process PID must be positive.")
    try:
        process = psutil.Process(pid)
        return RepairProcessIdentity(pid=pid, created_at=float(process.create_time()))
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as error:
        raise RepairProcessError(
            f"Could not identify repair handoff process: {pid}"
        ) from error


def wait_for_process_exit(
    identity: RepairProcessIdentity,
    *,
    timeout_seconds: float = 120.0,
) -> None:
    """Wait only for the captured process and reject PID reuse or timeout."""

    try:
        process = psutil.Process(identity.pid)
        observed_creation = float(process.create_time())
    except psutil.NoSuchProcess:
        return
    except (psutil.AccessDenied, OSError) as error:
        raise RepairProcessError(
            f"Could not inspect repair handoff process: {identity.pid}"
        ) from error
    if abs(observed_creation - identity.created_at) > 0.000_001:
        raise RepairProcessError(
            f"Repair handoff PID was reused before waiting: {identity.pid}"
        )
    try:
        process.wait(timeout=timeout_seconds)
    except psutil.NoSuchProcess:
        return
    except psutil.TimeoutExpired as error:
        raise RepairProcessError(
            f"Timed out waiting for repair handoff process: {identity.pid}"
        ) from error


__all__ = [
    "RepairProcessError",
    "RepairProcessIdentity",
    "capture_process_identity",
    "wait_for_process_exit",
]
