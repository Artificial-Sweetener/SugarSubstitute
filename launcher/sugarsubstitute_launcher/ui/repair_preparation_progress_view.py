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

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CaptionLabel  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from sugarsubstitute_shared.presentation.activity_progress_bar import (
    ActivityProgressBar,
)


class RepairPreparationProgressView(QWidget):
    """Animate activity while deriving fill exclusively from reported preparation work."""

    def __init__(self, parent: QWidget) -> None:
        """Build one Fluent bar slot and its localized stage caption."""
        super().__init__(parent)
        self._working = False
        self._label = cast(QLabel, CaptionLabel(self))
        self._label.setWordWrap(True)
        self._bar = ActivityProgressBar(self)
        self._bar.setObjectName("RepairPreparationProgress")
        self._bar.setFixedHeight(6)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._label)
        layout.addWidget(self._bar)
        self.hide()

    def set_working(self, working: bool) -> None:
        """Start or retire one visible preparation interval without resetting live progress."""
        if working and not self._working:
            self._bar.reset_progress()
            self._label.clear()
            self._bar.set_activity_enabled(True)
        elif not working:
            self._bar.set_activity_enabled(False)
        self._working = working
        self.setVisible(working)

    def set_progress(self, progress: PreparationProgress) -> None:
        """Display stage estimates and pulse once for the reported work."""
        if not self._working:
            return
        caption = preparation_stage_text(progress.stage)
        self._label.setText(caption)
        self._bar.setAccessibleName(caption)
        self._bar.set_progress(progress.completed_fraction, 1.0)
        self._bar.set_activity_enabled(progress.completed_fraction < 1)
        self._bar.record_activity()


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
