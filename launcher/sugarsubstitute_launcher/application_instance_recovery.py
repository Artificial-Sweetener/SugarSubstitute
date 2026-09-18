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

"""Retire verified unavailable instance owners within the current desktop session."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import psutil  # type: ignore[import-untyped]
from sugarsubstitute_shared.process_identity import ProcessIdentity
from launcher.sugarsubstitute_launcher.instance_process_control import (
    InstanceProcess,
    open_instance_process,
)
from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope


_LOGGER = logging.getLogger(__name__)
_TERMINATION_TIMEOUT_SECONDS = 5.0


def terminate_verified_process(
    identity: ProcessIdentity,
    *,
    scope: ApplicationProcessScope,
) -> bool:
    """Terminate the previously verified process without requiring responsive IPC."""

    expected_process_id = identity.pid
    if expected_process_id == os.getpid():
        _LOGGER.error("Refused to terminate the current recovery process")
        return False
    try:
        with open_instance_process(identity.pid) as process:
            try:
                return _terminate_retained_process(process, identity, scope=scope)
            except (OSError, psutil.Error):
                if _confirm_retained_exit(process, identity):
                    return True
                raise
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


def _terminate_retained_process(
    process: InstanceProcess,
    identity: ProcessIdentity,
    *,
    scope: ApplicationProcessScope,
) -> bool:
    """Verify and retire the same retained object throughout one recovery attempt."""
    expected_process_id = identity.pid
    if abs(float(process.create_time()) - identity.created_at) > 0.000_001:
        _LOGGER.warning(
            "Refused to terminate a reused instance PID",
            extra={"owner_process_id": identity.pid},
        )
        return False
    executable = Path(process.exe())
    if not scope.accepts_executable(executable) or not scope.accepts_invocation(
        executable, tuple(process.cmdline()), Path(process.cwd())
    ):
        _LOGGER.warning(
            "Refused to terminate instance owner outside the installation's process scope",
            extra={"owner_process_id": expected_process_id},
        )
        return False
    if sys.platform == "win32":
        from sugarsubstitute_shared.windows_process_security import (
            process_session_id,
        )

        if process_session_id(identity.pid) != process_session_id(os.getpid()):
            _LOGGER.warning(
                "Preserved instance owner in another Windows session",
                extra={"owner_process_id": identity.pid},
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


def _confirm_retained_exit(process: InstanceProcess, identity: ProcessIdentity) -> bool:
    """Resolve operation failure from terminal evidence while retaining native identity.

    Another launcher can finish retirement between any metadata or control call.
    Native query and termination errors alone do not prove a live failed owner.
    Preserve a live or unobservable process; only a confirmed exit permits election.
    """
    try:
        process.wait(timeout=_TERMINATION_TIMEOUT_SECONDS)
    except psutil.TimeoutExpired:
        return False
    except (OSError, psutil.Error):
        _LOGGER.warning(
            "Could not confirm instance exit after a native operation failed",
            extra={"owner_process_id": identity.pid},
            exc_info=True,
        )
        return False
    _LOGGER.info(
        "Confirmed retained instance exit after concurrent recovery operation failure",
        extra={"owner_process_id": identity.pid},
    )
    return True


__all__ = [
    "terminate_verified_process",
]
