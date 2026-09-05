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

from PySide6.QtWidgets import QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text

from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)


class ExistingModelsFolderQuestionPage(OnboardingPageFrame):
    """Ask whether setup should inspect an existing models folder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build a dedicated binary decision page with explicit action buttons."""

        super().__init__(
            title=app_text("Do you have an existing models folder?"),
            description=app_text(
                "Substitute can scan a folder you already use without changing its contents."
            ),
            icon=FIF.FOLDER,
            parent=parent,
        )
        self.setObjectName("OnboardingExistingModelsQuestionPage")
        self.content_column.setFixedWidth(520)
        self.hero_panel.center_compact_content(text_width=420)


__all__ = ["ExistingModelsFolderQuestionPage"]
