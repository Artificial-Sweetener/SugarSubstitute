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

"""Own the WinUI-style stretch-and-settle motion for a vertical indicator."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    QSequentialAnimationGroup,
    QVariantAnimation,
)

from substitute.presentation.motion import (
    CANVAS_TOOL_INDICATOR_EXTEND_DURATION_MS,
    CANVAS_TOOL_INDICATOR_SETTLE_DURATION_MS,
    resolve_motion_duration,
)

CanvasToolIndicatorFrameSink = Callable[[int, int], None]


class CanvasToolIndicatorMotion:
    """Stretch toward a selected row, then contract the trailing edge into it."""

    def __init__(
        self,
        *,
        parent: QObject,
        apply_frame: CanvasToolIndicatorFrameSink,
    ) -> None:
        """Create two asymmetric phases matching WinUI NavigationView motion."""

        self._apply_frame = apply_frame
        self._from_top = 0
        self._from_bottom = 1
        self._target_top = 0
        self._target_bottom = 1
        self._moves_down = True
        self._extend_duration_ms = resolve_motion_duration(
            CANVAS_TOOL_INDICATOR_EXTEND_DURATION_MS
        )
        self._settle_duration_ms = resolve_motion_duration(
            CANVAS_TOOL_INDICATOR_SETTLE_DURATION_MS
        )
        self.animation = QSequentialAnimationGroup(parent)
        self._extend = QVariantAnimation(self.animation)
        self._extend.setStartValue(0.0)
        self._extend.setEndValue(1.0)
        self._extend.setDuration(self._extend_duration_ms)
        self._extend.setEasingCurve(
            self._bezier_curve(
                first=QPointF(0.9, 0.1),
                second=QPointF(1.0, 0.2),
            )
        )
        self._extend.valueChanged.connect(self._apply_extend_frame)
        self._settle = QVariantAnimation(self.animation)
        self._settle.setStartValue(0.0)
        self._settle.setEndValue(1.0)
        self._settle.setDuration(self._settle_duration_ms)
        self._settle.setEasingCurve(
            self._bezier_curve(
                first=QPointF(0.1, 0.9),
                second=QPointF(0.2, 1.0),
            )
        )
        self._settle.valueChanged.connect(self._apply_settle_frame)
        self.animation.addAnimation(self._extend)
        self.animation.addAnimation(self._settle)

    @property
    def extend_duration_ms(self) -> int:
        """Return the leading-edge travel duration for deterministic tests."""

        return self._extend_duration_ms

    @property
    def settle_duration_ms(self) -> int:
        """Return the trailing-edge contraction duration."""

        return self._settle_duration_ms

    def start(
        self,
        *,
        from_top: int,
        from_height: int,
        target_top: int,
        target_height: int,
    ) -> None:
        """Start from the current visible frame without jumping on redirection."""

        self.animation.stop()
        self._from_top = from_top
        self._from_bottom = from_top + max(1, from_height)
        self._target_top = target_top
        self._target_bottom = target_top + max(1, target_height)
        self._moves_down = (
            self._target_top + self._target_bottom >= self._from_top + self._from_bottom
        )
        if self._extend_duration_ms + self._settle_duration_ms == 0:
            self._emit_frame(self._target_top, self._target_bottom)
            return
        self._emit_frame(self._from_top, self._from_bottom)
        self.animation.start()

    def stop(self) -> None:
        """Stop both phases without changing the currently painted frame."""

        self.animation.stop()

    def _apply_extend_frame(self, value: float) -> None:
        """Race the leading edge toward the target while the trailing edge holds."""

        progress = value
        if self._moves_down:
            top = self._from_top
            bottom = self._interpolate(
                self._from_bottom,
                self._target_bottom,
                progress,
            )
        else:
            top = self._interpolate(
                self._from_top,
                self._target_top,
                progress,
            )
            bottom = self._from_bottom
        self._emit_frame(top, bottom)

    def _apply_settle_frame(self, value: float) -> None:
        """Catch the trailing edge up and contract into the final marker."""

        progress = value
        if self._moves_down:
            top = self._interpolate(
                self._from_top,
                self._target_top,
                progress,
            )
            bottom = self._target_bottom
        else:
            top = self._target_top
            bottom = self._interpolate(
                self._from_bottom,
                self._target_bottom,
                progress,
            )
        self._emit_frame(top, bottom)

    def _emit_frame(self, top: int, bottom: int) -> None:
        """Normalize one edge pair and publish integer paint geometry."""

        normalized_top = min(top, bottom - 1)
        self._apply_frame(normalized_top, max(1, bottom - normalized_top))

    @staticmethod
    def _interpolate(start: int, end: int, progress: float) -> int:
        """Interpolate and round one geometry edge."""

        return round(start + (end - start) * progress)

    @staticmethod
    def _bezier_curve(
        *,
        first: QPointF,
        second: QPointF,
    ) -> QEasingCurve:
        """Build one cubic easing segment from WinUI's indicator control points."""

        curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
        curve.addCubicBezierSegment(first, second, QPointF(1.0, 1.0))
        return curve


__all__ = [
    "CanvasToolIndicatorFrameSink",
    "CanvasToolIndicatorMotion",
]
