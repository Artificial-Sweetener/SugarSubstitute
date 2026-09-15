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

"""Carry an exact outgoing supervisor identity through launcher handoff."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sugarsubstitute_shared.process_identity import ProcessIdentity


SUPERVISOR_HANDOFF_PID_ENV = "SUGAR_SUBSTITUTE_HANDOFF_SUPERVISOR_PID"
SUPERVISOR_HANDOFF_CREATED_AT_ENV = "SUGAR_SUBSTITUTE_HANDOFF_SUPERVISOR_CREATED_AT"


def with_supervisor_handoff(
    environment: Mapping[str, str],
    identity: ProcessIdentity,
) -> dict[str, str]:
    """Return a child environment bound to one exact outgoing supervisor."""

    handoff_environment = dict(environment)
    handoff_environment[SUPERVISOR_HANDOFF_PID_ENV] = str(identity.pid)
    handoff_environment[SUPERVISOR_HANDOFF_CREATED_AT_ENV] = repr(identity.created_at)
    return handoff_environment


def supervisor_handoff_present(environment: Mapping[str, str]) -> bool:
    """Return whether a complete outgoing-supervisor identity is present."""

    pid_present = SUPERVISOR_HANDOFF_PID_ENV in environment
    created_at_present = SUPERVISOR_HANDOFF_CREATED_AT_ENV in environment
    if pid_present != created_at_present:
        raise ValueError("Supervisor handoff identity is incomplete.")
    return pid_present


def consume_supervisor_handoff(
    environment: MutableMapping[str, str],
) -> ProcessIdentity | None:
    """Remove and return one complete validated supervisor handoff identity."""

    from sugarsubstitute_shared.process_identity import ProcessIdentity

    raw_pid = environment.pop(SUPERVISOR_HANDOFF_PID_ENV, None)
    raw_created_at = environment.pop(SUPERVISOR_HANDOFF_CREATED_AT_ENV, None)
    if raw_pid is None and raw_created_at is None:
        return None
    if raw_pid is None or raw_created_at is None:
        raise ValueError("Supervisor handoff identity is incomplete.")
    try:
        identity = ProcessIdentity(pid=int(raw_pid), created_at=float(raw_created_at))
    except ValueError as error:
        raise ValueError("Supervisor handoff identity is malformed.") from error
    if identity.pid <= 0 or identity.created_at <= 0:
        raise ValueError("Supervisor handoff identity is invalid.")
    return identity


__all__ = [
    "SUPERVISOR_HANDOFF_CREATED_AT_ENV",
    "SUPERVISOR_HANDOFF_PID_ENV",
    "consume_supervisor_handoff",
    "supervisor_handoff_present",
    "with_supervisor_handoff",
]
