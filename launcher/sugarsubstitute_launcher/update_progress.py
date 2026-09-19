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

"""Keep optional launcher update feedback outside update authority."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Protocol

from sugarsubstitute_shared.launch_splash import SplashActivity


_LOGGER = logging.getLogger(__name__)


class LauncherUpdateProgress(Protocol):
    """Receive user-visible launcher update progress."""

    def append_log(self, line: str) -> None:
        """Append one update progress line."""

    def start_activity(self, activity: SplashActivity) -> None:
        """Start or replace one independently animated update activity."""

    def clear_activity(self) -> None:
        """Stop the current update activity."""


class ResilientLauncherUpdateProgress:
    """Report update progress without granting the surface update authority."""

    def __init__(self, target: LauncherUpdateProgress | None) -> None:
        """Store the optional presentation target."""

        self._target = target

    def append_log(self, line: str) -> None:
        """Append one line when the presentation target remains available."""

        target = self._target
        if target is None:
            return
        self._deliver("append_log", lambda: target.append_log(line))

    def start_activity(self, activity: SplashActivity) -> None:
        """Start one activity when the presentation target remains available."""

        target = self._target
        if target is None:
            return
        self._deliver("start_activity", lambda: target.start_activity(activity))

    def clear_activity(self) -> None:
        """Clear activity state when the presentation target remains available."""

        target = self._target
        if target is None:
            return
        self._deliver("clear_activity", target.clear_activity)

    def _deliver(self, operation: str, delivery: Callable[[], None]) -> None:
        """Contain presentation failure and preserve the update transaction."""

        try:
            delivery()
        except Exception as error:
            _LOGGER.warning(
                "Launcher update progress delivery failed; continuing update | "
                "operation=%s progress_type=%s error_type=%s error=%s",
                operation,
                type(self._target).__name__,
                type(error).__name__,
                error,
                exc_info=True,
            )


__all__ = ["LauncherUpdateProgress", "ResilientLauncherUpdateProgress"]
