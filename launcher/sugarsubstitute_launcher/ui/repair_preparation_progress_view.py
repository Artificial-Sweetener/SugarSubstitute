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

"""Present immutable preparation stages through Fluent progress and activity bars."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QLabel,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CaptionLabel, IndeterminateProgressBar, ProgressBar  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text


class RepairPreparationProgressView(QWidget):
    """Animate activity while deriving fill exclusively from reported preparation work."""

    def __init__(self, parent: QWidget) -> None:
        """Build one Fluent bar slot and its localized stage caption."""
        super().__init__(parent)
        self._working = False
        self._label = cast(QLabel, CaptionLabel(self))
        self._label.setWordWrap(True)
        self._bar = cast(QProgressBar, ProgressBar(self))
        self._bar.setObjectName("RepairPreparationProgress")
        self._bar.setRange(0, 1000)
        self._bar.setFixedHeight(6)
        self._activity = IndeterminateProgressBar(self, start=False)
        self._activity.setObjectName("RepairPreparationActivity")
        self._activity.setFixedHeight(6)
        self._stack = QStackedWidget(self)
        self._stack.setFixedHeight(6)
        self._stack.addWidget(self._bar)
        self._stack.addWidget(self._activity)
        self._opacity = QGraphicsOpacityEffect(self._bar)
        self._bar.setGraphicsEffect(self._opacity)
        self._pulse = QPropertyAnimation(self._opacity, b"opacity", self)
        self._pulse.setDuration(1600)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.55)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._label)
        layout.addWidget(self._stack)
        self.hide()

    def set_working(self, working: bool) -> None:
        """Start or retire one visible preparation interval without resetting live progress."""
        if working and not self._working:
            self._bar.setValue(0)
            self._label.clear()
            self._stack.setCurrentWidget(self._activity)
            self._activity.start()
        elif not working:
            self._activity.stop()
            self._pulse.stop()
        self._working = working
        self.setVisible(working)

    def set_progress(self, progress: PreparationProgress) -> None:
        """Display stage estimates and retain animation throughout unfinished work."""
        if not self._working:
            return
        caption = preparation_stage_text(progress.stage)
        self._label.setText(caption)
        self._bar.setAccessibleName(caption)
        self._activity.setAccessibleName(caption)
        self._bar.setValue(round(progress.completed_fraction * 1000))
        if progress.completed_fraction > 0:
            self._activity.stop()
            self._stack.setCurrentWidget(self._bar)
            if progress.completed_fraction < 1:
                self._pulse.start()
            else:
                self._pulse.stop()
                self._opacity.setOpacity(1.0)


def preparation_stage_text(stage: PreparationStage) -> str:
    """Resolve installer-owned preparation captions at the presentation boundary."""
    match stage:
        case PreparationStage.RELEASE:
            return launcher_text("Checking the repair release")
        case PreparationStage.APPLICATION:
            return launcher_text("Preparing application files")
        case PreparationStage.LAUNCHER:
            return launcher_text("Preparing launcher files")
        case PreparationStage.VERIFY_APPLICATION:
            return launcher_text("Verifying application files")
        case PreparationStage.VERIFY_LAUNCHER:
            return launcher_text("Verifying launcher files")
        case PreparationStage.HELPER:
            return launcher_text("Preparing the repair helper")
        case PreparationStage.READY:
            return launcher_text("Repair is ready")
