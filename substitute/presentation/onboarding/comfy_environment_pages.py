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

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    BodyLabel,
    FluentIcon as FIF,
    PushButton,
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
            title="Close ComfyUI before setup continues",
            description=(
                "Substitute checks for running ComfyUI processes before changing "
                "local environments."
            ),
            icon=FIF.SYNC,
            eyebrow="Environment safety check",
            parent=parent,
        )
        self.setObjectName("OnboardingComfyPreflightPage")
        self.section = OnboardingSectionPanel(self)
        self.status_label = BodyLabel("Checking for running ComfyUI…", self)
        self.status_label.setObjectName("OnboardingComfyPreflightStatus")
        self.status_label.setWordWrap(True)
        self.section.content_layout.addWidget(self.status_label)
        self.close_button = PushButton("Close ComfyUI for me", self)
        self.close_button.setObjectName("OnboardingComfyPreflightCloseButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        self.section.content_layout.addWidget(self.close_button)
        self.explanation_panel = OnboardingInfoPanel(
            title="Why setup pauses here",
            description=(
                "Installing packages or changing model paths while ComfyUI is "
                "running can leave its environment in an inconsistent state."
            ),
            detail_lines=(
                "Continue becomes available automatically when ComfyUI stops.",
                "You can close it yourself or ask Substitute to close a verified process.",
            ),
            parent=self,
        )
        self.section.content_layout.addWidget(self.explanation_panel)
        self.body_layout.addWidget(self.section)

    def show_checking(self) -> None:
        """Render the nonblocking initial observation state."""

        self.status_label.setText("Checking for running ComfyUI…")
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: ComfyPreflightSnapshot) -> None:
        """Render one live process preflight observation."""

        if snapshot.can_continue:
            self.status_label.setText("ComfyUI is closed. Setup can continue.")
            self.close_button.hide()
            self.content_height_changed.emit()
            return
        count = len(snapshot.processes)
        noun = "process is" if count == 1 else "processes are"
        self.status_label.setText(
            f"{count} ComfyUI {noun} still running. Close ComfyUI to continue."
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
            title="We couldn't find ComfyUI's Python environment",
            description=(
                "Substitute could not identify the Python environment from the "
                "ComfyUI folder alone."
            ),
            icon=FIF.HELP,
            eyebrow="Find ComfyUI's Python environment",
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonChoicePage")
        section = OnboardingSectionPanel(self)
        self.choice_panel = OnboardingInfoPanel(
            title="Choose how to find it",
            description=(
                "Substitute can detect the environment from a running ComfyUI, or "
                "you can select the Python executable manually."
            ),
            detail_lines=(),
            parent=self,
        )
        section.content_layout.addWidget(self.choice_panel)
        choices = QHBoxLayout()
        self.process_button = PushButton("Detect from running ComfyUI", self)
        self.process_button.setObjectName("OnboardingAttachedPythonProcessChoice")
        self.process_button.clicked.connect(self.process_detection_requested.emit)
        choices.addWidget(self.process_button, 1)
        self.manual_button = PushButton("Select Python executable manually", self)
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
            title="Start ComfyUI",
            description=(
                "Substitute will identify the Python environment from the running "
                "ComfyUI process."
            ),
            icon=FIF.HELP,
            eyebrow="Detect ComfyUI's Python environment",
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonProcessPage")
        section = OnboardingSectionPanel(self)
        self.status_panel = OnboardingInfoPanel(
            title="Open ComfyUI yourself",
            description=(
                "Start this ComfyUI installation using your usual shortcut, script, "
                "or launcher. Keep this installer open; Substitute will detect it "
                "automatically."
            ),
            detail_lines=(
                "This screen updates as soon as the matching ComfyUI process appears.",
            ),
            parent=self,
        )
        self.status_panel.setObjectName("OnboardingAttachedPythonProcessStatus")
        section.content_layout.addWidget(self.status_panel)
        self.close_button = PushButton("Close ComfyUI and continue", self)
        self.close_button.setObjectName("OnboardingAttachedPythonProcessCloseButton")
        self.close_button.clicked.connect(self.close_requested.emit)
        self.close_button.hide()
        section.content_layout.addWidget(self.close_button)
        self.body_layout.addWidget(section)

    def reset(self) -> None:
        """Restore the initial live-detection guidance."""

        self.status_panel.title_label.setText("Open ComfyUI yourself")
        self.status_panel.description_label.setText(
            "Start this ComfyUI installation using your usual shortcut, script, "
            "or launcher. Keep this installer open; Substitute will detect it "
            "automatically."
        )
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: AttachedPythonRecoverySnapshot) -> None:
        """Render one current process-detection observation."""

        title_by_state = {
            AttachedPythonRecoveryState.WAITING_FOR_LAUNCH: "Open ComfyUI yourself",
            AttachedPythonRecoveryState.OTHER_COMFY_RUNNING: "A different ComfyUI is running",
            AttachedPythonRecoveryState.MULTIPLE_MATCHING: "More than one ComfyUI process was found",
            AttachedPythonRecoveryState.PYTHON_VALIDATION_FAILED: "That environment could not be verified",
            AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN: "Python environment found",
            AttachedPythonRecoveryState.READY: "Python environment ready",
        }
        self.status_panel.title_label.setText(title_by_state[snapshot.state])
        self.status_panel.description_label.setText(snapshot.detail)
        self.close_button.setVisible(snapshot.can_close)
        self.content_height_changed.emit()

    def show_failure(self, detail: str) -> None:
        """Render a process-observation failure without hiding route switching."""

        self.status_panel.title_label.setText("ComfyUI could not be checked yet")
        self.status_panel.description_label.setText(detail)
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
            title="Select ComfyUI's Python executable",
            description=(
                "Choose the Python executable used by this ComfyUI installation."
            ),
            icon=FIF.HELP,
            eyebrow="Select ComfyUI's Python environment",
            parent=parent,
        )
        self.setObjectName("OnboardingAttachedPythonManualPage")
        section = OnboardingSectionPanel(self)
        self.guidance_panel = OnboardingInfoPanel(
            title="Choose the Python your setup actually uses",
            description=(
                "Substitute already checked the usual environment locations in this "
                "ComfyUI folder."
            ),
            detail_lines=(
                "Select the executable used by the custom shortcut, script, launcher, "
                "or environment manager that starts ComfyUI.",
                "If you are not sure, use Detect from running ComfyUI instead.",
            ),
            parent=self,
        )
        section.content_layout.addWidget(self.guidance_panel)
        self.browse_button = PushButton("Browse for Python executable…", self)
        self.browse_button.setObjectName("OnboardingAttachedPythonManualBrowseButton")
        self.browse_button.clicked.connect(self.browse_requested.emit)
        section.content_layout.addWidget(self.browse_button)
        self.status_panel = OnboardingInfoPanel(
            title="Checking the selected Python executable…",
            description="Substitute is verifying that this Python belongs to ComfyUI.",
            detail_lines=(),
            parent=self,
        )
        self.status_panel.setObjectName("OnboardingAttachedPythonManualStatus")
        self.status_panel.hide()
        section.content_layout.addWidget(self.status_panel)
        self.close_button = PushButton("Close ComfyUI and continue", self)
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

        self.status_panel.title_label.setText(
            "Checking the selected Python executable…"
        )
        self.status_panel.description_label.setText(str(executable))
        self.status_panel.show()
        self.close_button.hide()
        self.content_height_changed.emit()

    def apply_snapshot(self, snapshot: AttachedPythonRecoverySnapshot) -> None:
        """Render shutdown or readiness after successful manual validation."""

        title_by_state = {
            AttachedPythonRecoveryState.WAITING_FOR_SHUTDOWN: "Python environment found",
            AttachedPythonRecoveryState.READY: "Python environment ready",
        }
        self.status_panel.title_label.setText(
            title_by_state.get(snapshot.state, "Checking the Python environment")
        )
        self.status_panel.description_label.setText(snapshot.detail)
        self.status_panel.show()
        self.close_button.setVisible(snapshot.can_close)
        self.content_height_changed.emit()

    def show_validation_failure(self, detail: str) -> None:
        """Render a failed selection while leaving Browse available."""

        self.status_panel.title_label.setText("That Python executable did not work")
        self.status_panel.description_label.setText(detail)
        self.status_panel.show()
        self.close_button.hide()
        self.content_height_changed.emit()


__all__ = [
    "AttachedPythonChoicePage",
    "AttachedPythonManualPage",
    "AttachedPythonProcessPage",
    "ComfyPreflightPage",
]
