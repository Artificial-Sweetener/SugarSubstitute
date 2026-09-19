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

"""Add a bounded activity sweep to Fluent determinate startup progress."""

from __future__ import annotations

from PySide6.QtCore import QAbstractAnimation, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ProgressBar, isDarkTheme  # type: ignore[import-untyped]
from substitute.presentation.motion import is_reduced_motion_enabled
from sugarsubstitute_shared.presentation.terminal.output_style import (
    TERMINAL_CORNER_RADIUS,
)


class SplashProgressBar(ProgressBar):  # type: ignore[misc]
    """Animate activity inside the completed fill without changing its value or track."""

    def __init__(self, parent: QWidget) -> None:
        """Keep the Fluent base renderer as the owner of fill and theme colors."""
        super().__init__(parent, useAni=False)
        self.setFixedHeight(4)
        self._console_attached = False
        self._phase = 0.0
        self._sweep = QVariantAnimation(self)
        self._sweep.setObjectName("SplashActivitySweep")
        self._sweep.setDuration(1800)
        self._sweep.setStartValue(0.0)
        self._sweep.setEndValue(1.0)
        self._sweep.setLoopCount(-1)
        self._sweep.valueChanged.connect(self._set_phase)

    def set_console_attached(self, attached: bool) -> None:
        """Join the console silhouette while keeping standalone Fluent geometry."""
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
        """Stop animation for hidden, terminal or reduced-motion surfaces."""
        enabled = enabled and not is_reduced_motion_enabled()
        if enabled:
            if self._sweep.state() != QAbstractAnimation.State.Running:
                self._sweep.start()
        else:
            self._sweep.stop()
            self.update()

    @property
    def activity_running(self) -> bool:
        """Expose whether the filled-region sweep is currently scheduled."""
        return self._sweep.state() == QAbstractAnimation.State.Running

    def record_activity(self) -> None:
        """Repaint observed work without resetting or stalling the ongoing sweep."""
        self.update()

    def _set_phase(self, phase: object) -> None:
        """Accept QVariantAnimation's floating-point frame value."""
        if isinstance(phase, (int, float)):
            self._phase = float(phase)
            self.update()

    def paintEvent(self, event: object) -> None:
        """Clip the moving highlight to the Fluent bar's rounded completed region."""
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
        if filled <= 0 or self._sweep.state() != QAbstractAnimation.State.Running:
            return
        clip = self._fill_clip(filled)
        band = max(12.0, filled * 0.35)
        center = -band + self._phase * (filled + 2 * band)
        gradient = QLinearGradient(center - band, 0, center + band, 0)
        gradient.setColorAt(0, QColor(255, 255, 255, 0))
        gradient.setColorAt(0.5, QColor(255, 255, 255, 65))
        gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setClipPath(clip)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), gradient)
