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

"""Render removable CivitAI model-link preview rows."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, ToolButton  # type: ignore[import-untyped]

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedStrongBodyLabel,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    thumbnail_pixmap,
)


class ModelLinkReadyRow(QFrame):
    """Show one validated model identity, preview, size, and removal action."""

    removal_requested = Signal(int)

    def __init__(self, card: RecommendationCardAsset, parent: QWidget) -> None:
        """Build a compact result row from one validated recommendation."""

        super().__init__(parent)
        recommendation = card.recommendation
        self.setObjectName("OnboardingModelLinkReadyRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(10)
        preview = QLabel(self)
        preview.setObjectName("OnboardingModelLinkThumbnail")
        preview.setFixedSize(44, 44)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = (
            thumbnail_pixmap(card.thumbnail) if card.thumbnail is not None else None
        )
        if pixmap is not None:
            preview.setPixmap(
                pixmap.scaled(
                    preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(preview)

        identity = QVBoxLayout()
        identity.setSpacing(1)
        identity.addWidget(LocalizedStrongBodyLabel(recommendation.model_name, self))
        size_gib = recommendation.size_bytes / (1024**3)
        identity.addWidget(
            LocalizedCaptionLabel(
                app_text(
                    "%1 · by %2 · %3 GiB",
                    recommendation.version_name,
                    recommendation.creator or "CivitAI",
                    f"{size_gib:.1f}",
                ),
                self,
            )
        )
        layout.addLayout(identity, 1)

        remove_button = ToolButton(FIF.DELETE, self)
        remove_button.setObjectName(
            f"OnboardingModelLinkRemove_{recommendation.version_id}"
        )
        remove_tooltip = render_application_text(
            app_text("Remove %1", recommendation.model_name)
        )
        set_fluent_tooltip_text(remove_button, remove_tooltip)
        remove_button.setAccessibleName(remove_tooltip)
        remove_button.clicked.connect(
            lambda: self.removal_requested.emit(recommendation.version_id)
        )
        layout.addWidget(remove_button)


__all__ = ["ModelLinkReadyRow"]
