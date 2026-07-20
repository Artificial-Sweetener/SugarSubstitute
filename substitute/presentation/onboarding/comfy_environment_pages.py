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

"""Render focused onboarding pages for live Comfy process guidance."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    app_text,
)

from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
)
from substitute.presentation.localization import LocalizedBodyLabel, LocalizedPushButton

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
)

from substitute.application.onboarding.comfy_environment_service import (
    AttachedPythonRecoverySnapshot,
    AttachedPythonRecoveryState,
    ComfyPreflightSnapshot,
)
from substitute.presentation.onboarding.onboarding_pages import (
    OnboardingInfoPanel,
    OnboardingPageFrame,
    OnboardingSectionPanel,
)


class ComfyPreflightPage(OnboardingPageFrame):
    """Block setup mutations while a confidently identified ComfyUI is running."""

    close_requested = Signal()
    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the responsive running-Comfy preflight page."""

        super().__init__(
            title=app_text("Close ComfyUI before setup continues"),
            description=(
                app_text(
                    "Substitute checks for running ComfyUI processes before changing "
                    "local environments."
                )
            ),
            icon=FIF.SYNC,
            eyebrow=app_text("Environment safety check"),
            parent=parent,
        )
        self.setObjectName("OnboardingComfyPreflightPage")
        self.section = OnboardingSectionPanel(self)
        self.status_label = LocalizedBodyLabel(
            app_text("Checking for running ComfyUI…"), self
        )
        self.status_label.setObjectName("OnboardingComfyPreflightStatus")
        self.status_label.setWordWrap(True)
        self.section.content_layout.addWidget(self.status_label)
        self.close_button = LocalizedPushButton(app_text("Close ComfyUI for me"), self)
        self.close_button.setObjectName("OnboardingComfyPreflightCloseButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        self.section.content_layout.addWidget(self.close_button)
        self.explanation_panel = OnboardingInfoPanel(
            title=app_text("Why setup pauses here"),
            description=(
                app_text(
                    "Installing packages or changing model paths while ComfyUI is "
                    "running can leave its environment in an inconsistent state."
                )
            ),
            detail_lines=(
                app_text(
                    "Continue becomes available automatically when ComfyUI stops."
                ),
                app_text(
                    "You can close it yourself or ask Substitute to close a verified "
                    "process."
                ),
            ),
            parent=self,
        )
        self.section.content_layout.addWidget(self.explanation_panel)
        self.body_layout.addWidget(self.section)

    def show_checking(self) -> None:
        """Render the nonblocking initial observation state."""

        set_localized_text(self.status_label, "Checking for running ComfyUI…")
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: ComfyPreflightSnapshot) -> None:
        """Render one live process preflight observation."""

        if snapshot.can_continue:
            set_localized_text(
                self.status_label, "ComfyUI is closed. Setup can continue."
            )
            self.close_button.hide()
            self.content_height_changed.emit()
            return
        count = len(snapshot.processes)
        if count == 1:
            set_localized_text(
                self.status_label,
                "1 ComfyUI process is still running. Close ComfyUI to continue.",
            )
        else:
            set_localized_text(
                self.status_label,
                "%1 ComfyUI processes are still running. Close ComfyUI to continue.",
                count,
            )
        self.close_button.setVisible(snapshot.can_close)
        self.content_height_changed.emit()


class AttachedPythonChoicePage(OnboardingPageFrame):
    """Present two equal recovery routes without beginning either action."""

    process_detection_requested = Signal()
    manual_selection_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the attached-Python recovery decision page."""

        super().__init__(
            title=app_text("We couldn't find ComfyUI's Python environment"),
            description=(
                app_text(
                    "Substitute could not identify the Python environment from the "
                    "ComfyUI folder alone."
                )
            ),
            icon=FIF.HELP,
            eyebrow=app_text("Find ComfyUI's Python environment"),
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonChoicePage")
        section = OnboardingSectionPanel(self)
        self.choice_panel = OnboardingInfoPanel(
            title=app_text("Choose how to find it"),
            description=(
                app_text(
                    "Substitute can detect the environment from a running ComfyUI, or "
                    "you can select the Python executable manually."
                )
            ),
            detail_lines=(),
            parent=self,
        )
        section.content_layout.addWidget(self.choice_panel)
        choices = QHBoxLayout()
        self.process_button = LocalizedPushButton(
            app_text("Detect from running ComfyUI"), self
        )
        self.process_button.setObjectName("OnboardingAttachedPythonProcessChoice")
        self.process_button.clicked.connect(self.process_detection_requested.emit)
        choices.addWidget(self.process_button, 1)
        self.manual_button = LocalizedPushButton(
            app_text("Select Python executable manually"), self
        )
        self.manual_button.setObjectName("OnboardingAttachedPythonManualChoice")
        self.manual_button.clicked.connect(self.manual_selection_requested.emit)
        choices.addWidget(self.manual_button, 1)
        section.content_layout.addLayout(choices)
        self.body_layout.addWidget(section)


class AttachedPythonProcessPage(OnboardingPageFrame):
    """Guide live process detection for an unusual attached environment."""

    close_requested = Signal()
    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the responsive running-Comfy detection page."""

        super().__init__(
            title=app_text("Start ComfyUI"),
            description=(
                app_text(
                    "Substitute will identify the Python environment from the running "
                    "ComfyUI process."
                )
            ),
            icon=FIF.HELP,
            eyebrow=app_text("Detect ComfyUI's Python environment"),
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonProcessPage")
        section = OnboardingSectionPanel(self)
        self.status_panel = OnboardingInfoPanel(
            title=app_text("Open ComfyUI yourself"),
            description=(
                app_text(
                    "Start this ComfyUI installation using your usual shortcut, script, "
                    "or launcher. Keep this installer open; Substitute will detect it "
                    "automatically."
                )
            ),
            detail_lines=(
                app_text(
                    "This screen updates as soon as the matching ComfyUI process appears."
                ),
            ),
            parent=self,
        )
        self.status_panel.setObjectName("OnboardingAttachedPythonProcessStatus")
        section.content_layout.addWidget(self.status_panel)
        self.close_button = LocalizedPushButton(
            app_text("Close ComfyUI and continue"), self
        )
        self.close_button.setObjectName("OnboardingAttachedPythonProcessCloseButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        section.content_layout.addWidget(self.close_button)
        self.body_layout.addWidget(section)

    def reset(self) -> None:
        """Restore the initial live-detection guidance."""

        set_localized_text(self.status_panel.title_label, "Open ComfyUI yourself")
        set_localized_text(
            self.status_panel.description_label,
            "Start this ComfyUI installation using your usual shortcut, script, "
            "or launcher. Keep this installer open; Substitute will detect it "
            "automatically.",
        )
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: AttachedPythonRecoverySnapshot) -> None:
        """Render one current process-detection observation."""

        title_by_state = {
            AttachedPythonRecoveryState.WAITING_FOR_LAUNCH: app_text(
                "Open ComfyUI yourself"
            ),
            AttachedPythonRecoveryState.OTHER_COMFY_RUNNING: app_text(
                "A different ComfyUI is running"
            ),
            AttachedPythonRecoveryState.MULTIPLE_MATCHING: app_text(
                "More than one ComfyUI process was found"
            ),
            AttachedPythonRecoveryState.PYTHON_VALIDATION_FAILED: app_text(
                "That environment could not be verified"
            ),
            AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN: app_text(
                "Python environment found"
            ),
            AttachedPythonRecoveryState.READY: app_text("Python environment ready"),
        }
        apply_application_text(
            self.status_panel.title_label, title_by_state[snapshot.state]
        )
        apply_application_text(self.status_panel.description_label, snapshot.detail)
        self.close_button.setVisible(snapshot.can_close)
        self.content_height_changed.emit()

    def show_failure(self, detail: ApplicationText) -> None:
        """Render a process-observation failure without hiding route switching."""

        set_localized_text(
            self.status_panel.title_label, "ComfyUI could not be checked yet"
        )
        apply_application_text(self.status_panel.description_label, detail)
        self.close_button.hide()
        self.content_height_changed.emit()


class AttachedPythonManualPage(OnboardingPageFrame):
    """Guide explicit Python selection and render its validation state."""

    browse_requested = Signal()
    close_requested = Signal()
    content_height_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the manual attached-Python selection page."""

        super().__init__(
            title=app_text("Select ComfyUI's Python executable"),
            description=(
                app_text(
                    "Choose the Python executable used by this ComfyUI installation."
                )
            ),
            icon=FIF.HELP,
            eyebrow=app_text("Select ComfyUI's Python environment"),
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonManualPage")
        section = OnboardingSectionPanel(self)
        self.guidance_panel = OnboardingInfoPanel(
            title=app_text("Choose the Python your setup actually uses"),
            description=(
                app_text(
                    "Substitute already checked the usual environment locations in this "
                    "ComfyUI folder."
                )
            ),
            detail_lines=(
                app_text(
                    "Select the executable used by the custom shortcut, script, "
                    "launcher, or environment manager that starts ComfyUI."
                ),
                app_text(
                    "If you are not sure, use Detect from running ComfyUI instead."
                ),
            ),
            parent=self,
        )
        section.content_layout.addWidget(self.guidance_panel)
        self.browse_button = LocalizedPushButton(
            app_text("Browse for Python executable…"), self
        )
        self.browse_button.setObjectName("OnboardingAttachedPythonManualBrowseButton")
        self.browse_button.clicked.connect(self.browse_requested.emit)
        section.content_layout.addWidget(self.browse_button)
        self.status_panel = OnboardingInfoPanel(
            title=app_text("Checking the selected Python executable…"),
            description=app_text(
                "Substitute is verifying that this Python belongs to ComfyUI."
            ),
            detail_lines=(),
            parent=self,
        )
        self.status_panel.setObjectName("OnboardingAttachedPythonManualStatus")
        self.status_panel.hide()
        section.content_layout.addWidget(self.status_panel)
        self.close_button = LocalizedPushButton(
            app_text("Close ComfyUI and continue"), self
        )
        self.close_button.setObjectName("OnboardingAttachedPythonManualCloseButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        section.content_layout.addWidget(self.close_button)
        self.body_layout.addWidget(section)

    def reset(self) -> None:
        """Restore manual-selection guidance before a file is chosen."""

        self.guidance_panel.show()
        self.browse_button.show()
        self.status_panel.hide()
        self.close_button.hide()
        self.content_height_changed.emit()

    def show_validation_started(self, executable: Path) -> None:
        """Show which selected executable is being verified."""

        set_localized_text(
            self.status_panel.title_label, "Checking the selected Python executable…"
        )
        self.status_panel.description_label.setText(str(executable))
        self.status_panel.show()
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: AttachedPythonRecoverySnapshot) -> None:
        """Render shutdown or readiness after successful manual validation."""

        title_by_state = {
            AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN: app_text(
                "Python environment found"
            ),
            AttachedPythonRecoveryState.READY: app_text("Python environment ready"),
        }
        apply_application_text(
            self.status_panel.title_label,
            title_by_state.get(
                snapshot.state,
                app_text("Checking the Python environment"),
            ),
        )
        apply_application_text(self.status_panel.description_label, snapshot.detail)
        self.status_panel.show()
        self.close_button.setVisible(snapshot.can_close)
        self.content_height_changed.emit()

    def show_validation_failure(self, detail: ApplicationText) -> None:
        """Render a failed selection while leaving Browse available."""

        set_localized_text(
            self.status_panel.title_label, "That Python executable did not work"
        )
        apply_application_text(self.status_panel.description_label, detail)
        self.status_panel.show()
        self.close_button.hide()
        self.content_height_changed.emit()


__all__ = [
    "AttachedPythonChoicePage",
    "AttachedPythonManualPage",
    "AttachedPythonProcessPage",
    "ComfyPreflightPage",
]
