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

"""Keep long-running setup activity visibly alive without invented progress."""

from __future__ import annotations

from collections.abc import Callable
import time

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QLabel

from sugarsubstitute_shared.launch_splash import format_activity_elapsed
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import apply_application_text


Clock = Callable[[], float]
_HEARTBEAT_INTERVAL_MILLISECONDS = 1_000


class SetupActivityPresenter(QObject):
    """Render monotonic elapsed activity while setup work remains active."""

    def __init__(
        self,
        *,
        label: QLabel,
        parent: QObject,
        clock: Clock = time.monotonic,
        heartbeat_interval_milliseconds: int = _HEARTBEAT_INTERVAL_MILLISECONDS,
    ) -> None:
        """Bind one visible label to an independently advancing heartbeat."""

        if heartbeat_interval_milliseconds <= 0:
            raise ValueError("Setup heartbeat interval must be positive.")
        super().__init__(parent)
        self._label = label
        self._clock = clock
        self._started_at: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(heartbeat_interval_milliseconds)
        self._timer.timeout.connect(self.refresh)

    @property
    def active(self) -> bool:
        """Return whether setup activity is currently advancing."""

        return self._started_at is not None

    def start(self) -> None:
        """Begin a fresh elapsed activity generation and render immediately."""

        self._started_at = self._clock()
        self.refresh()
        self._timer.start()

    def stop(self) -> None:
        """Freeze the last truthful elapsed value after work ends."""

        self._timer.stop()
        self._started_at = None

    @Slot()
    def refresh(self) -> None:
        """Render the current monotonic duration without estimating completion."""

        started_at = self._started_at
        if started_at is None:
            return
        elapsed_seconds = max(0.0, self._clock() - started_at)
        apply_application_text(
            self._label,
            app_text(
                "Setup is active — %1 elapsed",
                format_activity_elapsed(elapsed_seconds),
            ),
        )


__all__ = ["SetupActivityPresenter"]
