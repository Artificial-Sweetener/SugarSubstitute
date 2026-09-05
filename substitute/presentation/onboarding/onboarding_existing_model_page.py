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

"""Render the first-run existing-model-folder decision."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text

from substitute.presentation.onboarding.onboarding_binary_choice import (
    OnboardingBinaryChoice,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)


class ExistingModelsFolderQuestionPage(OnboardingPageFrame):
    """Ask whether setup should inspect an existing models folder."""

    answer_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build a dedicated binary decision page with explicit action buttons."""

        super().__init__(
            title=app_text("Do you have an existing models folder?"),
            description=app_text(
                "Choose the ComfyUI models folder you already use. Substitute will scan it without changing its contents."
            ),
            icon=FIF.FOLDER,
            eyebrow=app_text("Folders"),
            parent=parent,
        )
        self.setObjectName("OnboardingExistingModelsQuestionPage")
        self.choice = OnboardingBinaryChoice(
            yes_object_name="OnboardingExistingModelsYes",
            no_object_name="OnboardingExistingModelsNo",
            parent=self,
        )
        self.yes_button = self.choice.yes_button
        self.no_button = self.choice.no_button
        self.choice.answer_changed.connect(self.answer_changed)
        self.body_layout.addWidget(
            self.choice,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

    def answer(self) -> bool | None:
        """Return the explicit Yes/No selection or None before a choice."""

        return self.choice.answer()

    def set_answer(self, answer: bool | None) -> None:
        """Restore a prior answer when navigating back to the question."""

        self.choice.set_answer(answer)


__all__ = ["ExistingModelsFolderQuestionPage"]
