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

from PySide6.QtCore import QSignalBlocker, Qt, Signal, Slot
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    CaptionLabel,
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
from sugarsubstitute_shared.presentation.activity_progress_bar import (
    ActivityProgressBar,
)


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
        self.progress_bar = ActivityProgressBar(self)
        self.progress_bar.setObjectName("LauncherInstallProgress")
        self.progress_bar.setRange(0, len(InstallationStage))
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)
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
        self._working = value.completed < value.total
        if not value.finished and not self._stopping:
            self._activity.start(_stage_title(value.stage))
        if not self._working:
            self._activity.stop()
            self.activity_label.setText(
                launcher_text("Waiting for the setup window to open.")
            )
        self._update_activity()

    def append_log(self, message: str) -> None:
        """Retain diagnostic records without replacing the user's stage headline."""
        self.progress_log.append_line(f"{message}\n")
        if self._working and self.isVisible():
            self.progress_bar.record_activity()

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
        self._update_activity()
        self.activity_label.setText(message)
        with QSignalBlocker(self.details_button):
            self.details_button.setChecked(True)
        self._set_details_visible(True)

    def hideEvent(self, event: QHideEvent) -> None:
        """Release animation work when the progress surface is hidden or closed."""
        self.progress_bar.set_activity_enabled(False)
        super().hideEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        """Rearm visible activity without manufacturing an activity event."""
        self._title.setText(launcher_text("Setting up SugarSubstitute"))
        self.details_button.setText(
            launcher_text("Hide details")
            if self.details_button.isChecked()
            else launcher_text("Show details")
        )
        super().showEvent(event)
        self._update_activity()

    def _update_activity(self) -> None:
        """Arm activity pulses without changing workflow-owned completion."""
        self.progress_bar.set_activity_enabled(self._working and self.isVisible())

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
