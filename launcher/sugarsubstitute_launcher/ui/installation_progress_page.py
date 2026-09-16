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

"""Present workflow-owned installation milestones with a Fluent progress bar."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import (
    QAbstractAnimation,
    QPropertyAnimation,
    QSignalBlocker,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
    ProgressBar,
    IndeterminateProgressBar,
    PushButton,
    SubtitleLabel,
    FluentIcon as FIF,
)

from launcher.sugarsubstitute_launcher.application.installation.progress import (
    InstallationProgress,
    InstallationStage,
)
from launcher.sugarsubstitute_launcher.application.installation.models import (
    InstalledApplication,
)
from launcher.sugarsubstitute_launcher.localized_text import launcher_text
from launcher.sugarsubstitute_launcher.ui.installation_activity_presenter import (
    InstallationActivityPresenter,
)
from launcher.sugarsubstitute_launcher.ui.installer_page_layout import (
    configure_installer_page,
    build_installer_hero,
)
from sugarsubstitute_shared.presentation.terminal import TerminalOutputView


class InstallationProgressPage(QFrame):
    """Keep completion, ongoing activity, and optional diagnostics distinct."""

    geometry_changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        """Build native-style progress whose fill changes only at real milestones."""
        super().__init__(parent)
        layout = configure_installer_page(self, "LauncherProgressPage")
        hero, text_layout = build_installer_hero(self, FIF.SYNC)
        self._title = cast(
            QLabel, SubtitleLabel(launcher_text("Setting up SugarSubstitute"), self)
        )
        self._title.setObjectName("OnboardingPageTitle")
        self.activity_label = cast(
            QLabel, BodyLabel(launcher_text("Getting things ready…"), self)
        )
        self.activity_label.setObjectName("LauncherCurrentActivity")
        self.activity_label.setWordWrap(True)
        text_layout.addWidget(self._title)
        text_layout.addWidget(self.activity_label)
        self._activity = InstallationActivityPresenter(
            label=self.activity_label, parent=self
        )
        self._step = cast(QLabel, CaptionLabel(self))
        text_layout.addWidget(self._step)
        layout.addLayout(hero)
        layout.addSpacing(12)
        self.progress_bar = cast(QProgressBar, ProgressBar(self))
        self.progress_bar.setObjectName("LauncherInstallProgress")
        self.progress_bar.setRange(0, len(InstallationStage))
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self._opacity = QGraphicsOpacityEffect(self.progress_bar)
        self._opacity.setOpacity(1.0)
        self.progress_bar.setGraphicsEffect(self._opacity)
        self._pulse = QPropertyAnimation(self._opacity, b"opacity", self)
        self._pulse.setDuration(1600)
        self._pulse.setStartValue(1.0)
        self._pulse.setKeyValueAt(0.5, 0.55)
        self._pulse.setEndValue(1.0)
        self._pulse.setLoopCount(-1)
        self._progress_stack = QStackedWidget(self)
        self._progress_stack.setFixedHeight(6)
        self._preparation_activity: IndeterminateProgressBar = IndeterminateProgressBar(
            self, start=False
        )
        self._preparation_activity.setFixedHeight(6)
        self._progress_stack.addWidget(self.progress_bar)
        self._progress_stack.addWidget(self._preparation_activity)
        layout.addWidget(self._progress_stack)
        self.details_button = cast(
            QPushButton, PushButton(launcher_text("Show details"), self)
        )
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._set_details_visible)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.progress_log = TerminalOutputView(
            self,
            min_height=220,
            max_height=280,
            use_qfluent_chrome=False,
            observe_qfluent_theme=False,
        )
        self.progress_log.hide()
        layout.addWidget(self.progress_log)
        layout.addStretch(1)
        self._working = False
        self._stopping = False

    @Slot(object)
    def set_progress(self, value: object) -> None:
        """Project queued workflow events without interpreting console output."""
        if not isinstance(value, InstallationProgress):
            raise TypeError("Installation progress requires a workflow milestone.")
        self.progress_bar.setValue(value.completed)
        self._step.setText(
            launcher_text("Step %1 of %2", int(value.stage) + 1, value.total)
        )
        self.progress_bar.setAccessibleName(_stage_title(value.stage))
        self.progress_bar.setAccessibleDescription(self._step.text())
        self._preparation_activity.setAccessibleName(_stage_title(value.stage))
        self._preparation_activity.setAccessibleDescription(self._step.text())
        self._working = value.completed < value.total
        if not value.finished and not self._stopping:
            self._activity.start(_stage_title(value.stage))
        if not self._working:
            self._activity.stop()
            self.activity_label.setText(
                launcher_text("Waiting for the setup window to open.")
            )
        self._update_pulse()

    def append_log(self, message: str) -> None:
        """Retain diagnostic records without replacing the user's stage headline."""
        self.progress_log.append_line(f"{message}\n")
        if self._working and self.isVisible():
            self._pulse.setCurrentTime(0)

    def record_installed_application(self, application: InstalledApplication) -> None:
        """Expose verified payload identity in the installer's optional details."""
        self.append_log(
            launcher_text("Installed app payload version: %1", application.app_version)
        )
        self.append_log(
            launcher_text("App entrypoint: %1", application.layout.app_entrypoint)
        )

    def show_stopping(self, message: str) -> None:
        """Keep a requested safe close visible while the current work finishes."""
        self._stopping = True
        self._activity.start(message)
        self.append_log(message)

    def show_failure(self, message: str) -> None:
        """Stop activity and expose details while preserving completed progress."""
        self._working = False
        self._stopping = False
        self._activity.stop()
        self._update_pulse()
        self.activity_label.setText(message)
        with QSignalBlocker(self.details_button):
            self.details_button.setChecked(True)
        self._set_details_visible(True)

    def hideEvent(self, event: QHideEvent) -> None:
        """Release animation work when the progress surface is hidden or closed."""
        self._pulse.stop()
        self._preparation_activity.stop()
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Resume visible activity without advancing completion."""
        self._title.setText(launcher_text("Setting up SugarSubstitute"))
        self.details_button.setText(
            launcher_text("Hide details")
            if self.details_button.isChecked()
            else launcher_text("Show details")
        )
        super().showEvent(event)
        self._update_pulse()

    def _update_pulse(self) -> None:
        """Animate activity independently from the determinate Fluent bar value."""
        preparing = self._working and self.progress_bar.value() == 0
        self._progress_stack.setCurrentWidget(
            self._preparation_activity if preparing else self.progress_bar
        )
        if preparing and self.isVisible():
            if not self._preparation_activity.isStarted():
                self._preparation_activity.start()
        else:
            self._preparation_activity.stop()
        if self._working and self.isVisible() and not preparing:
            if self._pulse.state() is not QAbstractAnimation.State.Running:
                self._pulse.start()
        else:
            self._pulse.stop()
            self._opacity.setOpacity(1.0)

    def _set_details_visible(self, visible: bool) -> None:
        """Resize the containing page when optional technical details change."""
        self.progress_log.setVisible(visible)
        self.details_button.setText(
            launcher_text("Hide details") if visible else launcher_text("Show details")
        )
        self.geometry_changed.emit()


def _stage_title(stage: InstallationStage) -> str:
    """Translate workflow identity at the presentation boundary."""
    return {
        InstallationStage.PREPARATION: launcher_text(
            "Preparing SugarSubstitute install."
        ),
        InstallationStage.APPLICATION: launcher_text("Installing SugarSubstitute"),
        InstallationStage.RUNTIME: launcher_text(
            "Installing Python runtime and app dependencies."
        ),
        InstallationStage.HANDOFF: launcher_text("Starting SugarSubstitute setup."),
    }[stage]
