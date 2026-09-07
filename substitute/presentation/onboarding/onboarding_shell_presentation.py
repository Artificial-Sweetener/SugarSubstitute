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

"""Own installer-shell progress and issue presentation for onboarding."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, IconWidget  # type: ignore[import-untyped]

from substitute.presentation.localization import LocalizedCaptionLabel
from substitute.presentation.onboarding.onboarding_models import OnboardingPageId
from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)


@dataclass(frozen=True)
class ProgressPresentation:
    """Describe the compact installer progress copy for one page."""

    step_number: int
    step_count: int
    title: ApplicationText
    helper: ApplicationText


PROGRESS_BY_PAGE: dict[OnboardingPageId, ProgressPresentation] = {
    OnboardingPageId.WELCOME: ProgressPresentation(
        step_number=1,
        step_count=4,
        title=app_text("Choose a folder"),
        helper=app_text("You can change the ComfyUI connection later."),
    ),
    OnboardingPageId.COMFY_PREFLIGHT: ProgressPresentation(
        step_number=1,
        step_count=4,
        title=app_text("Check ComfyUI"),
        helper=app_text("Setup continues automatically once ComfyUI is closed."),
    ),
    OnboardingPageId.TARGET_MODE: ProgressPresentation(
        step_number=2,
        step_count=4,
        title=app_text("Pick a setup"),
        helper=app_text("Most people should start with the first option."),
    ),
    OnboardingPageId.MANAGED_LOCAL: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Confirm the details"),
        helper=app_text("The defaults usually work well for first-time setup."),
    ),
    OnboardingPageId.ATTACHED_LOCAL: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Confirm the details"),
        helper=app_text("Choose the existing ComfyUI folder Substitute should launch."),
    ),
    OnboardingPageId.ATTACHED_PYTHON_CHOICE: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Find ComfyUI's environment"),
        helper=app_text("Choose how Substitute should identify ComfyUI's Python."),
    ),
    OnboardingPageId.ATTACHED_PYTHON_PROCESS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Detect ComfyUI's environment"),
        helper=app_text(
            "Start ComfyUI yourself; Substitute will detect it automatically."
        ),
    ),
    OnboardingPageId.ATTACHED_PYTHON_MANUAL: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Select ComfyUI's environment"),
        helper=app_text(
            "Choose the Python executable that this ComfyUI installation uses."
        ),
    ),
    OnboardingPageId.REMOTE: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Confirm the details"),
        helper=app_text("Use the server address this computer can reach."),
    ),
    OnboardingPageId.EXISTING_MODELS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Choose models"),
        helper=app_text("Keep the defaults or point Substitute at your folders."),
    ),
    OnboardingPageId.FOLDERS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Choose folders"),
        helper=app_text("Keep the defaults or point Substitute at your folders."),
    ),
    OnboardingPageId.MODEL_RECOMMENDATIONS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Choose models"),
        helper=app_text("Review CivitAI's popular models for each family."),
    ),
    OnboardingPageId.MODEL_DOWNLOAD_REVIEW: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Review downloads"),
        helper=app_text("Nothing downloads until setup is confirmed."),
    ),
    OnboardingPageId.INTEGRATIONS: ProgressPresentation(
        step_number=3,
        step_count=4,
        title=app_text("Helpful extras"),
        helper=app_text("Helpful extras can be changed later in Settings."),
    ),
    OnboardingPageId.PROVISIONING: ProgressPresentation(
        step_number=4,
        step_count=4,
        title=app_text("Finish setup"),
        helper=app_text("This can take a little while the first time."),
    ),
    OnboardingPageId.COMPLETION: ProgressPresentation(
        step_number=4,
        step_count=4,
        title=app_text("Ready to launch"),
        helper=app_text("You're almost done."),
    ),
}


class OnboardingIssuePanel(QFrame):
    """Render repair-mode issues in a supportive inline surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the issue panel used for repair and incomplete setup states."""

        super().__init__(parent)
        self.setObjectName("OnboardingIssuePanel")
        self._issue_title: ApplicationText = app_text(
            "Let's get this setup back on track"
        )
        self._issue_body: ApplicationText = ""
        self._issue_detail = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)

        self.icon_widget = IconWidget(FIF.INFO, self)
        self.icon_widget.setFixedSize(16, 16)
        header_row.addWidget(self.icon_widget, alignment=Qt.AlignmentFlag.AlignTop)

        self.title_label = LocalizedCaptionLabel(
            app_text("Let's get this setup back on track"), self
        )
        self.title_label.setObjectName("OnboardingIssueTitle")
        self.title_label.setWordWrap(True)
        header_row.addWidget(self.title_label, 1, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header_row)

        self.body_label = LocalizedCaptionLabel("", self)
        self.body_label.setObjectName("OnboardingIssueBody")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

    def set_issue_content(
        self,
        *,
        title: ApplicationText,
        body: ApplicationText,
        detail: str,
    ) -> None:
        """Render the issue headline, user guidance, and technical detail."""

        apply_application_text(self.title_label, title)
        apply_application_text(self.body_label, body)
        set_fluent_tooltip_text(self, detail)
        self._issue_title = title
        self._issue_body = body
        self._issue_detail = detail

    def setText(self, text: str) -> None:
        """Preserve the label-like API used by existing callers."""

        self.set_issue_content(title=self._issue_title, body=text, detail="")

    def text(self) -> str:
        """Return the rendered issue copy for contract tests."""

        return "\n".join(
            part
            for part in (
                render_application_text(self._issue_title),
                render_application_text(self._issue_body),
                self._issue_detail,
            )
            if part
        )


__all__ = [
    "OnboardingIssuePanel",
    "PROGRESS_BY_PAGE",
    "ProgressPresentation",
]
