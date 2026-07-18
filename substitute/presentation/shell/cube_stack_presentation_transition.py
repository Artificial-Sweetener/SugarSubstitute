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

"""Animate typed cube-stack presentation frames without owning shell widgets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Property, QPropertyAnimation, Signal

from substitute.presentation.motion import (
    CUBE_STACK_MODE_DURATION_MS,
    TRANSFORM_EASING_CURVE,
    resolve_motion_duration,
    stop_animation,
)
from substitute.presentation.shell.cube_stack_presentation_models import (
    CubeStackPresentationFrame,
    CubeStackPresentationMode,
    interpolate_cube_stack_frame,
)


class CubeStackPresentationTransition(QObject):
    """Retarget animation from the current rendered frame to one exact endpoint."""

    transitionFinished = Signal(object, int)

    def __init__(
        self,
        *,
        read_frame: Callable[[], CubeStackPresentationFrame],
        apply_frame: Callable[[CubeStackPresentationFrame], None],
        duration_resolver: Callable[[int], int] = resolve_motion_duration,
        parent: QObject | None = None,
    ) -> None:
        """Store typed frame ports and configure the production Qt animator."""

        super().__init__(parent)
        self._read_frame = read_frame
        self._apply_frame = apply_frame
        self._duration_resolver = duration_resolver
        self._progress = 0.0
        self._start_frame = read_frame()
        self._target_frame = self._start_frame
        self._target_mode = CubeStackPresentationMode.EXPANDED
        self._generation = 0
        self._active_generation = 0
        self._animating = False
        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.finished.connect(self._finish_active_transition)

    def transition_to(
        self,
        mode: CubeStackPresentationMode,
        frame: CubeStackPresentationFrame,
        *,
        animated: bool = True,
    ) -> int:
        """Retarget from live geometry and return the new completion identity."""

        self._animation.stop()
        self._animating = False
        self._generation += 1
        self._active_generation = self._generation
        self._target_mode = mode
        self._start_frame = self._read_frame()
        self._target_frame = frame
        self._progress = 0.0
        duration_ms = (
            self._duration_resolver(CUBE_STACK_MODE_DURATION_MS) if animated else 0
        )
        if duration_ms <= 0 or self._start_frame == self._target_frame:
            self._apply_frame(self._target_frame)
            self._finish_active_transition()
            return self._active_generation

        self._animating = True
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(duration_ms)
        self._animation.setEasingCurve(TRANSFORM_EASING_CURVE)
        self._animation.start()
        return self._active_generation

    def stop(self) -> None:
        """Stop the current animation without claiming target completion."""

        stop_animation(self._animation)
        self._animating = False

    @property
    def is_animating(self) -> bool:
        """Return whether a presentation transition is currently running."""

        return self._animating

    @property
    def active_generation(self) -> int:
        """Return the identity of the most recently requested transition."""

        return self._active_generation

    def _get_progress(self) -> float:
        """Return the current normalized animation progress."""

        return self._progress

    def setProgress(self, progress: float) -> None:  # noqa: N802
        """Apply one interpolated frame for Qt's property animation."""

        self._progress = max(0.0, min(1.0, float(progress)))
        self._apply_frame(
            interpolate_cube_stack_frame(
                self._start_frame,
                self._target_frame,
                self._progress,
            )
        )

    def _finish_active_transition(self) -> None:
        """Commit the exact target and emit its stable completion identity."""

        self._animating = False
        self._progress = 1.0
        self._apply_frame(self._target_frame)
        self.transitionFinished.emit(self._target_mode, self._active_generation)

    progress = Property(float, _get_progress, setProgress)


__all__ = ["CubeStackPresentationTransition"]
