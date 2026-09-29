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

"""Provide deterministic Qt surfaces and clocks to shared motion tests."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.motion.timeline import MotionClock
from tools.editor_projection_rig.qt_harness import ensure_qapplication


class ManualMotionClock:
    """Expose deterministic frame and completion control to motion tests."""

    def __init__(self) -> None:
        """Initialize the clock in its stopped state."""

        self._running = False
        self._frame: Callable[[float], None] | None = None
        self._finished: Callable[[], None] | None = None

    def start(
        self,
        *,
        duration_ms: int,
        easing: QEasingCurve.Type | QEasingCurve,
        frame: Callable[[float], None],
        finished: Callable[[], None],
    ) -> None:
        """Retain callbacks until the test advances or finishes the clock."""

        _ = duration_ms, easing
        self._running = True
        self._frame = frame
        self._finished = finished

    def stop(self) -> None:
        """Stop timing without publishing completion."""

        self._running = False
        self._frame = None
        self._finished = None

    def is_running(self) -> bool:
        """Return whether the test clock is active."""

        return self._running

    def advance(self, elapsed_ms: float) -> None:
        """Publish one deterministic elapsed-time frame."""

        if self._frame is not None:
            self._frame(elapsed_ms)

    def finish(self) -> None:
        """Publish natural completion exactly once."""

        finished = self._finished
        self._running = False
        self._frame = None
        self._finished = None
        if finished is not None:
            finished()


def manual_clock_factory(clock: MotionClock) -> Callable[[QObject], MotionClock]:
    """Return a factory that injects one deterministic test clock."""

    return lambda _parent: clock


def mounted_surface() -> tuple[QWidget, QLabel]:
    """Return one visible surface and target suitable for capture."""

    ensure_qapplication()
    viewport = QWidget()
    viewport.resize(320, 180)
    target = QLabel("Committed card", viewport)
    target.setGeometry(30, 40, 180, 52)
    target.show()
    viewport.show()
    QApplication.processEvents()
    return viewport, target


__all__ = ["ManualMotionClock", "manual_clock_factory", "mounted_surface"]
