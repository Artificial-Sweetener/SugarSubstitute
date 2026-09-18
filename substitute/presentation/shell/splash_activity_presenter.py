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
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Signal, Slot

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


class ActivityFrameScheduler(Protocol):
    """Schedule presenter-owned frame refreshes."""

    def start(self) -> None:
        """Begin delivering frame callbacks."""

    def stop(self) -> None:
        """Stop delivering frame callbacks."""


ActivityFrameSchedulerFactory = Callable[
    [QObject, int, Callable[[], None]], ActivityFrameScheduler
]


class _QtActivityFrameScheduler(QObject):
    """Adapt a repeating Qt timer to the splash frame scheduler contract."""

    def __init__(
        self,
        *,
        parent: QObject,
        interval_milliseconds: int,
        callback: Callable[[], None],
    ) -> None:
        """Own one timer whose lifetime follows the presenter."""

        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_milliseconds)
        self._timer.timeout.connect(callback)

    def start(self) -> None:
        """Begin periodic callback delivery."""

        self._timer.start()

    def stop(self) -> None:
        """Stop periodic callback delivery."""

        self._timer.stop()


def _create_qt_activity_frame_scheduler(
    parent: QObject,
    interval_milliseconds: int,
    callback: Callable[[], None],
) -> ActivityFrameScheduler:
    """Create the production Qt-backed frame scheduler."""

    return _QtActivityFrameScheduler(
        parent=parent,
        interval_milliseconds=interval_milliseconds,
        callback=callback,
    )


class SplashActivityPresenter(QObject):
    """Own splash activity timing independently from blocking producer work."""

    textChanged = Signal(str)

    def __init__(
        self,
        *,
        stream: TerminalOutputStream,
        parent: QObject | None = None,
        clock: Clock = time.monotonic,
        frame_interval_milliseconds: int = _DEFAULT_FRAME_INTERVAL_MILLISECONDS,
        scheduler_factory: ActivityFrameSchedulerFactory = (
            _create_qt_activity_frame_scheduler
        ),
    ) -> None:
        """Bind activity rendering to one terminal stream and monotonic clock."""

        if frame_interval_milliseconds <= 0:
            raise ValueError("Splash activity frame interval must be positive.")
        super().__init__(parent)
        self._stream = stream
        self._clock = clock
        self._activity: SplashActivity | None = None
        self._detail: SplashActivity | None = None
        self._closed = False
        self._started_at = 0.0
        self._scheduler = scheduler_factory(
            self,
            frame_interval_milliseconds,
            self.refresh,
        )

    @property
    def active(self) -> bool:
        """Return whether an activity currently owns the terminal tail row."""

        return self._activity is not None or self._detail is not None

    def start(self, activity: SplashActivity) -> None:
        """Start or replace the active operation and render its first frame."""

        if self._closed:
            return
        self._activity = activity
        self._detail = None
        self._started_at = self._clock()
        self.refresh()
        self._scheduler.start()

    def set_detail(self, message: str) -> None:
        """Refine operation copy without resetting the shared elapsed-time policy."""
        if self._closed:
            return
        from sugarsubstitute_shared.localization import app_text
        from sugarsubstitute_shared.presentation.localization import (
            render_application_text,
        )

        if not self.active:
            self._started_at = self._clock()
        operation = message.rstrip(".…。")
        self._detail = SplashActivity(
            initial_text=operation,
            long_wait_text=render_application_text(
                app_text("%1…\nThis is taking longer than usual", operation)
            ),
            extended_wait_text=render_application_text(
                app_text("%1…\nThis is taking much longer than expected", operation)
            ),
        )
        self.refresh()
        self._scheduler.start()

    def clear_detail(self) -> None:
        """Restore the containing operation's current wait level after a milestone."""
        self._detail = None
        if self._activity is None:
            self.clear()
        else:
            self.refresh()

    def clear(self) -> None:
        """Stop activity animation and remove its transient terminal row."""

        self._scheduler.stop()
        self._activity = None
        self._detail = None
        self._stream.clear_transient_line()
        self.textChanged.emit("")

    def restore_after_log(self, record: str) -> None:
        """Restore activity after a durable log replaced its transient row."""

        if self.active and not _is_transient_record(record):
            self.refresh()

    @Slot()
    def refresh(self) -> None:
        """Replace the terminal tail with the current time-derived frame."""

        activity = self._detail or self._activity
        if activity is None:
            return
        elapsed_seconds = max(0.0, self._clock() - self._started_at)
        text = render_splash_activity(activity, elapsed_seconds)
        if self._activity is not None:
            terminal_text = render_splash_activity(self._activity, elapsed_seconds)
            self._stream.append_line(f"{terminal_text}\r")
        self.textChanged.emit(text)

    def shutdown(self) -> None:
        """Permanently stop frame delivery without mutating terminal history."""

        self._closed = True
        self._scheduler.stop()
        self._activity = None
        self._detail = None


def _is_transient_record(record: str) -> bool:
    """Return whether a record already owns the terminal redraw row."""

    return record.endswith("\r") and not record.endswith("\r\n")


__all__ = [
    "ActivityFrameScheduler",
    "ActivityFrameSchedulerFactory",
    "SplashActivityPresenter",
]
