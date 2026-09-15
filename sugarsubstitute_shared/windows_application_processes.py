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

"""Discover earlier instances using kernel identity when their IPC is unavailable."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from pathlib import Path

import psutil  # type: ignore[import-untyped]

from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.windows_process_security import (
    process_session_id,
    process_user_sid,
)

_LOGGER = logging.getLogger(__name__)


def find_previous_application_process(
    executable: Path, *, accepts_invocation: Callable[[Sequence[str], Path], bool]
) -> ProcessIdentity | None:
    """Find the oldest earlier launcher in this executable's user and session.

    Verify the caller's executable with Windows rather than trusting arguments or
    Python globals. Exclude newer launches so concurrent recovery cannot end a
    replacement that started after this request. No process is terminated here.
    """
    expected = executable.resolve()
    try:
        caller = psutil.Process(os.getpid())
        if Path(caller.exe()).resolve() != expected:
            return None
        caller_created = float(caller.create_time())
        user = process_user_sid(caller.pid)
        session = process_session_id(caller.pid)
    except (OSError, psutil.Error):
        _LOGGER.exception("Could not verify the recovery launcher's OS identity")
        return None
    candidates: list[ProcessIdentity] = []
    for pid in psutil.pids():
        if pid == caller.pid:
            continue
        try:
            process = psutil.Process(pid)
            image = Path(process.exe())
            if (
                image.name.casefold() != expected.name.casefold()
                or image.resolve() != expected
            ):
                continue
            created = float(process.create_time())
            if created >= caller_created:
                continue
            if process_user_sid(pid) != user or process_session_id(pid) != session:
                continue
            if not accepts_invocation(tuple(process.cmdline()), Path(process.cwd())):
                continue
            if not process.is_running():
                continue
            candidates.append(ProcessIdentity(pid, created))
        except psutil.NoSuchProcess:
            continue
        except (OSError, psutil.Error):
            _LOGGER.debug(
                "Process unavailable during recovery discovery",
                exc_info=True,
                extra={"process_id": pid},
            )
    candidate = min(
        candidates, key=lambda item: (item.created_at, item.pid), default=None
    )
    if candidate is not None:
        _LOGGER.info(
            "Identified an earlier installed application process for explicit recovery",
            extra={
                "process_id": candidate.pid,
                "process_created_at": candidate.created_at,
            },
        )
    return candidate
