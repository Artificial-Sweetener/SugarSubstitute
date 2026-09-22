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

"""Render monotonic completion and bounded observed-activity sweeps."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ProgressBar, isDarkTheme  # type: ignore[import-untyped]

from sugarsubstitute_shared.presentation.fluent_motion import (
    is_reduced_motion_enabled,
)
from sugarsubstitute_shared.presentation.terminal.output_style import (
    TERMINAL_CORNER_RADIUS,
)


ACTIVITY_PROGRESS_SCALE = 1000


class ActivityProgressBar(ProgressBar):  # type: ignore[misc]
    """Own one progress projection and activity behavior for long-running work."""

    def __init__(self, parent: QWidget) -> None:
        """Keep the Fluent base renderer as the owner of fill and theme colors."""
        super().__init__(parent, useAni=False)
        self.setFixedHeight(4)
        self.setRange(0, ACTIVITY_PROGRESS_SCALE)
        self.setValue(0)
        self._visible_fraction = 0.0
        self._activity_enabled = False
        self._activity_pending = False
        self._console_attached = False
        self._phase = 0.0
        self._sweep = QVariantAnimation(self)
        self._sweep.setObjectName("ProgressActivitySweep")
        self._sweep.setDuration(1800)
        self._sweep.setStartValue(0.0)
        self._sweep.setEndValue(1.0)
        self._sweep.setLoopCount(1)
        self._sweep.valueChanged.connect(self._set_phase)
        self._sweep.finished.connect(self._continue_pending_activity)

    def reset_progress(self) -> None:
        """Start a new attempt whose completion may begin below the prior attempt."""

        self._visible_fraction = 0.0
        self.setValue(0)

    def set_progress(self, completed: int | float, total: int | float) -> None:
        """Project valid producer units without letting visible completion regress."""

        if total <= 0 or completed < 0 or completed > total:
            raise ValueError("Progress requires 0 <= completed <= total and total > 0.")
        self._visible_fraction = max(self._visible_fraction, completed / total)
        self.setValue(round(self._visible_fraction * ACTIVITY_PROGRESS_SCALE))

    @property
    def visible_fraction(self) -> float:
        """Return the nondecreasing fraction currently presented to the user."""

        return self._visible_fraction

    def set_console_attached(self, attached: bool) -> None:
        """Join a console silhouette while keeping standalone Fluent geometry."""
        self._console_attached = attached
        self.setFixedHeight(TERMINAL_CORNER_RADIUS if attached else 4)
        self.update()

    def _fill_clip(self, filled: float) -> QPainterPath:
        """Clip fill and activity to one outline with a flat console-facing edge."""
        clip = QPainterPath()
        if self._console_attached:
            radius = TERMINAL_CORNER_RADIUS
            clip.addRoundedRect(QRectF(0, 0, self.width(), radius * 2), radius, radius)
            completed = QPainterPath()
            completed.addRect(QRectF(0, 0, filled, self.height()))
            return clip.intersected(completed)
        radius = self.height() / 2
        clip.addRoundedRect(QRectF(0, 0, filled, self.height()), radius, radius)
        return clip

    def set_activity_enabled(self, enabled: bool) -> None:
        """Arm real activity pulses or stop a surface that cannot display them."""
        self._activity_enabled = enabled and not is_reduced_motion_enabled()
        if not self._activity_enabled:
            self._activity_pending = False
            self._sweep.stop()
            self.update()

    @property
    def activity_running(self) -> bool:
        """Expose whether the filled-region sweep is currently scheduled."""
        return self._sweep.state() == QAbstractAnimation.State.Running

    def record_activity(self) -> None:
        """Coalesce observed work into bounded sweeps without changing completion."""
        if not self._activity_enabled:
            return
        if self._sweep.state() == QAbstractAnimation.State.Running:
            self._activity_pending = True
        else:
            self._sweep.start()
        self.update()

    def _continue_pending_activity(self) -> None:
        """Run one more sweep when work arrived during the preceding sweep."""

        if not self._activity_enabled or not self._activity_pending:
            return
        self._activity_pending = False
        self._sweep.start()

    def _set_phase(self, phase: object) -> None:
        """Accept QVariantAnimation's floating-point frame value."""
        if isinstance(phase, (int, float)):
            self._phase = float(phase)
            self.update()

    def paintEvent(self, event: object) -> None:
        """Clip the moving highlight to the Fluent bar's completed region."""
        if not self._console_attached:
            super().paintEvent(event)
        total = self.maximum() - self.minimum()
        filled = (
            self.width() * (self.value() - self.minimum()) / total if total > 0 else 0
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._console_attached:
            background = (
                QColor(255, 255, 255, 18) if isDarkTheme() else QColor(0, 0, 0, 12)
            )
            painter.fillPath(self._fill_clip(self.width()), background)
            painter.fillPath(self._fill_clip(filled), self.barColor())
        if self._sweep.state() != QAbstractAnimation.State.Running:
            return
        activity_width = filled if filled > 0 else float(self.width())
        clip = self._fill_clip(activity_width)
        band = max(12.0, activity_width * 0.35)
        center = -band + self._phase * (activity_width + 2 * band)
        gradient = QLinearGradient(center - band, 0, center + band, 0)
        gradient.setColorAt(0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 65))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setClipPath(clip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), gradient)


__all__ = ["ActivityProgressBar"]
