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

"""Run remote-capable managed-startup steps through one sticky fallback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from substitute.shared.logging.logger import (
    get_logger,
    log_info,
    log_warning_exception,
)
from sugarsubstitute_shared.startup_remote_access import StartupRemoteAccess


TResult = TypeVar("TResult")
_LOGGER = get_logger("infrastructure.comfy.managed_startup_remote_steps")


@dataclass(frozen=True, slots=True)
class ManagedStartupRemoteStepResult(Generic[TResult]):
    """Describe whether one remote-capable startup step completed."""

    completed: bool
    value: TResult | None = None


class ManagedStartupRemoteSteps:
    """Enforce one-way degradation across managed startup maintenance."""

    def __init__(self, remote_access: StartupRemoteAccess) -> None:
        """Use the launch-scoped remote-access state as the authority."""

        self._remote_access = remote_access

    @property
    def degraded(self) -> bool:
        """Return whether this launch is fixed to installed local state."""

        return not self._remote_access.allows_remote_work

    def run(
        self,
        *,
        operation: str,
        action: Callable[[], TResult],
    ) -> ManagedStartupRemoteStepResult[TResult]:
        """Run one step or suppress it after the first remote failure."""

        if self.degraded:
            log_info(
                _LOGGER,
                "Skipped remote-capable managed startup work after degradation",
                operation=operation,
                degradation_reason=self._remote_access.degradation_reason,
            )
            return ManagedStartupRemoteStepResult(completed=False)
        try:
            return ManagedStartupRemoteStepResult(completed=True, value=action())
        except Exception as error:  # noqa: BLE001 - this boundary guarantees local fallback.
            self._remote_access.degrade(reason=operation)
            log_warning_exception(
                _LOGGER,
                "Managed startup remote work degraded; using installed local state",
                error=error,
                operation=operation,
            )
            return ManagedStartupRemoteStepResult(completed=False)


__all__ = ["ManagedStartupRemoteStepResult", "ManagedStartupRemoteSteps"]
