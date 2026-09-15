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

"""Keep launcher installation activity visibly alive between producer records."""

from __future__ import annotations

from collections.abc import Callable
import time

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QLabel

from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.launch_splash import format_activity_elapsed


Clock = Callable[[], float]
_HEARTBEAT_INTERVAL_MILLISECONDS = 1_000


class InstallationActivityPresenter(QObject):
    """Project the latest real operation with an independent elapsed heartbeat."""

    def __init__(
        self,
        *,
        label: QLabel,
        parent: QObject,
        clock: Clock = time.monotonic,
        heartbeat_interval_milliseconds: int = _HEARTBEAT_INTERVAL_MILLISECONDS,
    ) -> None:
        """Bind a progress label to one monotonic activity generation."""

        if heartbeat_interval_milliseconds <= 0:
            raise ValueError("Installation heartbeat interval must be positive.")
        super().__init__(parent)
        self._label = label
        self._clock = clock
        self._operation: str | None = None
        self._started_at = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(heartbeat_interval_milliseconds)
        self._timer.timeout.connect(self.refresh)

    @property
    def active(self) -> bool:
        """Return whether an operation currently owns the progress headline."""

        return self._operation is not None

    def start(self, operation: str) -> None:
        """Start timing the latest producer-confirmed operation."""

        normalized = operation.strip()
        if not normalized:
            raise ValueError("Installation activity must not be empty.")
        self._operation = normalized
        self._started_at = self._clock()
        self.refresh()
        self._timer.start()

    def stop(self) -> None:
        """Stop the heartbeat while retaining the last rendered headline."""

        self._timer.stop()
        self._operation = None

    @Slot()
    def refresh(self) -> None:
        """Render activity from the monotonic clock, independent from worker work."""

        operation = self._operation
        if operation is None:
            return
        elapsed = format_activity_elapsed(self._clock() - self._started_at)
        self._label.setText(launcher_text("%1 — %2 elapsed", operation, elapsed))


__all__ = ["InstallationActivityPresenter"]
