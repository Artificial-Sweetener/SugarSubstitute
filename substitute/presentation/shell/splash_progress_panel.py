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

"""Present startup completion independently from activity and optional diagnostics."""

from __future__ import annotations

from typing import cast
from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import IndeterminateProgressBar, ProgressBar  # type: ignore[import-untyped]
from substitute.presentation.localization import LocalizedBodyLabel, LocalizedPushButton
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import set_localized_text
from sugarsubstitute_shared.launch_splash.progress import SplashProgress


class SplashProgressPanel(QWidget):
    """Own the visible startup status, honest fill and expandable diagnostic surface."""

    def __init__(self, *, details: QWidget, parent: QWidget | None = None) -> None:
        """Mount supplied diagnostics without taking ownership of startup execution."""
        super().__init__(parent)
        self._complete = False
        self._failed = False
        self._progress_status = ""
        self._activity_status = ""
        self.details = details
        self.status = LocalizedBodyLabel(app_text("Loading..."), self)
        self.status.setWordWrap(True)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        self.progress = cast(QProgressBar, ProgressBar(self, useAni=False))
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.activity: IndeterminateProgressBar = IndeterminateProgressBar(
            self, start=False
        )
        self._bars = QStackedWidget(self)
        self._bars.setFixedHeight(6)
        self._bars.addWidget(self.activity)
        self._bars.addWidget(self.progress)
        self._opacity = QGraphicsOpacityEffect(self.progress)
        self._opacity.setOpacity(1.0)
        self.progress.setGraphicsEffect(self._opacity)
        self._pulse = QPropertyAnimation(self._opacity, b"opacity", self)
        self._pulse.setDuration(1600)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.55)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        self.details_button = LocalizedPushButton(app_text("Show details"), self)
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._show_details)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.status)
        layout.addWidget(self._bars)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(details, 1)
        self.details.hide()

    def set_progress(self, value: SplashProgress, *, status: str) -> None:
        """Display producer-owned completion and translated status without estimation."""
        if self._failed:
            return
        self._progress_status = status
        self.status.setText(self._activity_status or status)
        self.progress.setRange(0, value.total)
        self.progress.setValue(value.completed)
        self.progress.setAccessibleName(status)
        self.activity.setAccessibleName(status)
        self._complete = value.completed == value.total
        self._bars.setCurrentWidget(self.progress if value.completed else self.activity)
        self._update_activity()

    def set_activity_status(self, message: str) -> None:
        """Project operation feedback while retaining authoritative completion units."""
        if self._failed:
            return
        self._activity_status = message
        if message or self._progress_status:
            self.status.setText(message or self._progress_status)
        else:
            set_localized_text(self.status, app_text("Loading..."))

    def show_failure(self, message: str) -> None:
        """Retain terminal failure and expose diagnostics without advancing completion."""
        self._failed = True
        self.status.setText(message)
        self._bars.setCurrentWidget(self.progress)
        self.details_button.setChecked(True)
        self._update_activity()

    def record_activity(self) -> None:
        """Pulse on actual output without changing completion or the step label."""
        if self._pulse.state() == QAbstractAnimation.State.Running:
            self._pulse.setCurrentTime(0)

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop hidden animation work while retaining stage state."""
        self.activity.stop()
        self._pulse.stop()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Resume visible activity without claiming additional completed work."""
        super().showEvent(event)
        self._update_activity()

    def _update_activity(self) -> None:
        """Animate only the currently visible unfinished progress surface."""
        active = self.isVisible() and not self._complete and not self._failed
        indeterminate = self._bars.currentWidget() is self.activity
        if active and indeterminate:
            if not self.activity.isStarted():
                self.activity.start()
        else:
            self.activity.stop()
        if active and not indeterminate:
            if self._pulse.state() != QAbstractAnimation.State.Running:
                self._pulse.start()
        else:
            self._pulse.stop()
            self._opacity.setOpacity(1.0)

    def _show_details(self, visible: bool) -> None:
        """Expose retained diagnostics without altering execution or progress state."""
        self.details.setVisible(visible)
        set_localized_text(
            self.details_button,
            app_text("Hide details") if visible else app_text("Show details"),
        )
