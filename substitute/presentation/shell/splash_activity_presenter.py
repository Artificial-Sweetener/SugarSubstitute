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

"""Present one independently animated activity in the splash terminal tail."""

from __future__ import annotations

from collections.abc import Callable
import time

from PySide6.QtCore import QObject, QTimer, Slot

from sugarsubstitute_shared.launch_splash.activity import (
    ACTIVITY_FRAME_SECONDS,
    SplashActivity,
    render_splash_activity,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (
    TerminalOutputStream,
)

Clock = Callable[[], float]
_DEFAULT_FRAME_INTERVAL_MILLISECONDS = int(ACTIVITY_FRAME_SECONDS * 1000)


class SplashActivityPresenter(QObject):
    """Own splash activity timing independently from blocking producer work."""

    def __init__(
        self,
        *,
        stream: TerminalOutputStream,
        parent: QObject | None = None,
        clock: Clock = time.monotonic,
        frame_interval_milliseconds: int = _DEFAULT_FRAME_INTERVAL_MILLISECONDS,
    ) -> None:
        """Bind activity rendering to one terminal stream and monotonic clock."""

        if frame_interval_milliseconds <= 0:
            raise ValueError("Splash activity frame interval must be positive.")
        super().__init__(parent)
        self._stream = stream
        self._clock = clock
        self._activity: SplashActivity | None = None
        self._started_at = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(frame_interval_milliseconds)
        self._timer.timeout.connect(self.refresh)

    @property
    def active(self) -> bool:
        """Return whether an activity currently owns the terminal tail row."""

        return self._activity is not None

    def start(self, activity: SplashActivity) -> None:
        """Start or replace the active operation and render its first frame."""

        self._activity = activity
        self._started_at = self._clock()
        self.refresh()
        self._timer.start()

    def clear(self) -> None:
        """Stop activity animation and remove its transient terminal row."""

        self._timer.stop()
        self._activity = None
        self._stream.clear_transient_line()

    def restore_after_log(self, record: str) -> None:
        """Restore activity after a durable log replaced its transient row."""

        if self._activity is not None and not _is_transient_record(record):
            self.refresh()

    @Slot()
    def refresh(self) -> None:
        """Replace the terminal tail with the current time-derived frame."""

        activity = self._activity
        if activity is None:
            return
        elapsed_seconds = max(0.0, self._clock() - self._started_at)
        self._stream.append_line(
            f"{render_splash_activity(activity, elapsed_seconds)}\r"
        )

    def shutdown(self) -> None:
        """Stop scheduling frames without mutating terminal history."""

        self._timer.stop()
        self._activity = None


def _is_transient_record(record: str) -> bool:
    """Return whether a record already owns the terminal redraw row."""

    return record.endswith("\r") and not record.endswith("\r\n")


__all__ = ["SplashActivityPresenter"]
