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

"""Drive one deterministic clock for a complete surface transition."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Protocol, TypeAlias

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QObject, QVariantAnimation


class MotionClock(Protocol):
    """Describe the replaceable clock consumed by a motion timeline."""

    def start(
        self,
        *,
        duration_ms: int,
        easing: QEasingCurve.Type | QEasingCurve,
        frame: Callable[[float], None],
        finished: Callable[[], None],
    ) -> None:
        """Start publishing elapsed values and one terminal callback."""

    def stop(self) -> None:
        """Stop timing without publishing completion."""

    def is_running(self) -> bool:
        """Return whether the clock is actively publishing values."""


MotionClockFactory: TypeAlias = Callable[[QObject], MotionClock]


class QtMotionClock(QObject):
    """Adapt one Qt value animation into the shared clock contract."""

    def __init__(self, parent: QObject) -> None:
        """Initialize an idle clock owned by the supplied timeline."""

        super().__init__(parent)
        self._animation: QVariantAnimation | None = None

    def start(
        self,
        *,
        duration_ms: int,
        easing: QEasingCurve.Type | QEasingCurve,
        frame: Callable[[float], None],
        finished: Callable[[], None],
    ) -> None:
        """Start a Qt-backed elapsed-time animation."""

        self.stop()
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(float(duration_ms))
        animation.setDuration(duration_ms)
        animation.setEasingCurve(easing)
        animation.valueChanged.connect(lambda value: frame(float(value)))
        animation.finished.connect(
            lambda active=animation: self._finish_if_current(active, finished)
        )
        self._animation = animation
        animation.start()

    def stop(self) -> None:
        """Stop and dispose the active Qt animation."""

        animation = self._animation
        self._animation = None
        if animation is None:
            return
        if animation.state() is not QAbstractAnimation.State.Stopped:
            animation.stop()
        animation.deleteLater()

    def is_running(self) -> bool:
        """Return whether the Qt animation is currently running."""

        animation = self._animation
        return (
            animation is not None
            and animation.state() is QAbstractAnimation.State.Running
        )

    def _finish_if_current(
        self,
        animation: QVariantAnimation,
        finished: Callable[[], None],
    ) -> None:
        """Publish completion only for the currently owned animation."""

        if animation is not self._animation:
            return
        self._animation = None
        animation.deleteLater()
        finished()


class MotionTimeline(QObject):
    """Own one replaceable animation clock shared by all transition targets."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        clock_factory: MotionClockFactory | None = None,
    ) -> None:
        """Initialize the timeline without active animation state."""

        super().__init__(parent)
        factory = clock_factory or QtMotionClock
        self._clock = factory(self)
        self._generation: int | None = None

    @property
    def generation(self) -> int | None:
        """Return the active generation when timing is running."""

        return self._generation

    def start(
        self,
        *,
        generation: int,
        duration_ms: int,
        easing: QEasingCurve.Type | QEasingCurve,
        frame: Callable[[float], None],
        finished: Callable[[int], None],
    ) -> None:
        """Replace active timing and publish normalized progress frames."""

        self.stop()
        if duration_ms <= 0:
            frame(1.0)
            finished(generation)
            return
        self._generation = generation
        self._clock.start(
            duration_ms=duration_ms,
            easing=easing,
            frame=partial(self._frame_if_current, generation, frame=frame),
            finished=partial(self._finish_if_current, generation, finished),
        )

    def stop(self) -> None:
        """Stop and dispose the active clock without publishing completion."""

        self._generation = None
        self._clock.stop()

    def is_running(self) -> bool:
        """Return whether one animation clock is active."""

        return self._generation is not None and self._clock.is_running()

    def _frame_if_current(
        self,
        generation: int,
        elapsed_ms: float,
        frame: Callable[[float], None],
    ) -> None:
        """Publish a frame only for the active generation."""

        if generation == self._generation:
            frame(elapsed_ms)

    def _finish_if_current(
        self,
        generation: int,
        finished: Callable[[int], None],
    ) -> None:
        """Publish completion only for the currently owned clock."""

        if generation != self._generation:
            return
        self._generation = None
        finished(generation)


__all__ = [
    "MotionClock",
    "MotionClockFactory",
    "MotionTimeline",
    "QtMotionClock",
]
