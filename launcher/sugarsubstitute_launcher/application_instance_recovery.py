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

"""Verify explicit termination of an unreachable active instance owner."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import psutil  # type: ignore[import-untyped]
from sugarsubstitute_shared.process_identity import ProcessIdentity


_LOGGER = logging.getLogger(__name__)
_TERMINATION_TIMEOUT_SECONDS = 5.0


def terminate_verified_process(
    identity: ProcessIdentity,
    *,
    expected_executable: Path,
) -> bool:
    """Terminate the previously verified process without requiring responsive IPC."""

    expected_process_id = identity.pid
    if expected_process_id == os.getpid():
        _LOGGER.error("Refused to terminate the current recovery process")
        return False
    try:
        process = psutil.Process(identity.pid)
        if abs(float(process.create_time()) - identity.created_at) > 0.000_001:
            _LOGGER.warning(
                "Refused to terminate a reused instance PID",
                extra={"owner_process_id": identity.pid},
            )
            return False
        if Path(process.exe()).resolve() != expected_executable.resolve():
            _LOGGER.warning(
                "Refused to terminate instance owner with a different executable",
                extra={"owner_process_id": expected_process_id},
            )
            return False
        process.terminate()
        _LOGGER.info(
            "Requested termination of verified unresponsive instance owner",
            extra={"owner_process_id": expected_process_id},
        )
        try:
            process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
        except psutil.TimeoutExpired:
            _LOGGER.warning(
                "Verified instance owner ignored termination; forcing exit",
                extra={"owner_process_id": expected_process_id},
            )
            process.kill()
            process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
        _LOGGER.info(
            "Verified unresponsive instance owner exited",
            extra={"owner_process_id": expected_process_id},
        )
        return True
    except psutil.NoSuchProcess:
        _LOGGER.info(
            "Verified instance owner has already exited",
            extra={"owner_process_id": expected_process_id},
        )
        return True
    except (OSError, psutil.Error):
        _LOGGER.exception(
            "Could not terminate the verified unresponsive instance owner",
            extra={"owner_process_id": expected_process_id},
        )
        return False


__all__ = [
    "terminate_verified_process",
]
