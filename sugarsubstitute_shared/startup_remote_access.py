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

"""Own the sticky remote-access decision for one application launch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


STARTUP_REMOTE_DEGRADED_ENV = "SUGARSUBSTITUTE_STARTUP_REMOTE_DEGRADED"


@dataclass(slots=True)
class StartupRemoteAccess:
    """Track whether automatic remote work remains safe during one launch."""

    _degradation_reason: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> StartupRemoteAccess:
        """Restore the launcher's sticky degradation handoff."""

        if environment.get(STARTUP_REMOTE_DEGRADED_ENV) == "1":
            return cls(_degradation_reason="launcher_remote_work_failed")
        return cls()

    @property
    def allows_remote_work(self) -> bool:
        """Return whether another automatic remote operation may begin."""

        return self._degradation_reason is None

    @property
    def degradation_reason(self) -> str | None:
        """Return the first failure that fixed this launch to local fallbacks."""

        return self._degradation_reason

    def degrade(self, *, reason: str) -> None:
        """Latch the first remote failure for the remainder of this launch."""

        if self._degradation_reason is None:
            self._degradation_reason = reason

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """Encode this launch decision into one isolated child environment."""

        child_environment = dict(environment)
        if self.allows_remote_work:
            child_environment.pop(STARTUP_REMOTE_DEGRADED_ENV, None)
        else:
            child_environment[STARTUP_REMOTE_DEGRADED_ENV] = "1"
        return child_environment


__all__ = ["STARTUP_REMOTE_DEGRADED_ENV", "StartupRemoteAccess"]
