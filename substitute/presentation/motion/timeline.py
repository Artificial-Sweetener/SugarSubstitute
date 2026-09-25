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

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QObject, QVariantAnimation


class MotionTimeline(QObject):
    """Own one replaceable animation clock shared by all transition targets."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the timeline without active animation state."""

        super().__init__(parent)
        self._animation: QVariantAnimation | None = None
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
        easing: QEasingCurve.Type,
        frame: Callable[[float], None],
        finished: Callable[[int], None],
    ) -> None:
        """Replace active timing and publish normalized progress frames."""

        self.stop()
        if duration_ms <= 0:
            frame(1.0)
            finished(generation)
            return
        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(float(duration_ms))
        animation.setDuration(duration_ms)
        animation.setEasingCurve(QEasingCurve(easing))
        animation.valueChanged.connect(lambda value: frame(float(value)))
        animation.finished.connect(
            lambda active=animation, token=generation: self._finish_if_current(
                active,
                token,
                finished,
            )
        )
        self._generation = generation
        self._animation = animation
        animation.start()

    def stop(self) -> None:
        """Stop and dispose the active clock without publishing completion."""

        animation = self._animation
        self._animation = None
        self._generation = None
        if animation is None:
            return
        if animation.state() is not QAbstractAnimation.State.Stopped:
            animation.stop()
        animation.deleteLater()

    def is_running(self) -> bool:
        """Return whether one animation clock is active."""

        animation = self._animation
        return (
            animation is not None
            and animation.state() is QAbstractAnimation.State.Running
        )

    def _finish_if_current(
        self,
        animation: QVariantAnimation,
        generation: int,
        finished: Callable[[int], None],
    ) -> None:
        """Publish completion only for the currently owned clock."""

        if animation is not self._animation or generation != self._generation:
            return
        self._animation = None
        self._generation = None
        animation.deleteLater()
        finished(generation)


__all__ = ["MotionTimeline"]
