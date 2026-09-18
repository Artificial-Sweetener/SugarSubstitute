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

"""Present one removable exact-model download card."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import render_application_text

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_recommendations import ModelInstallFile
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
    thumbnail_image,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)

from substitute.presentation.onboarding.onboarding_download_text import (
    format_model_size,
)

_REMOVE_BUTTON_STYLE = """
QToolButton {
    background-color: rgba(10, 12, 18, 194);
    border: 1px solid rgba(255, 255, 255, 158);
    border-radius: 7px;
}
QToolButton:hover {
    background-color: rgba(188, 42, 72, 240);
    border-color: rgba(255, 255, 255, 224);
}
QToolButton:pressed {
    background-color: rgba(151, 27, 52, 250);
}
"""


class DownloadCartCard(QFrame):
    """Present one exact selected model as a removable checkout item."""

    remove_requested = Signal(int)

    def __init__(
        self,
        *,
        item: ModelInstallFile,
        card: RecommendationCardAsset,
        parent: QWidget,
    ) -> None:
        """Build a title-washed portrait with concise family and size metadata."""

        super().__init__(parent)
        self.setObjectName("OnboardingDownloadCartCard")
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        image = _card_image(card)
        self.portrait = RecommendationPortrait(
            image=image,
            title=item.display_name,
            thumbnail_failed=card.thumbnail_failed,
            selected=False,
            accessible_name=item.display_name,
            metadata=f"{item.family_id.value.upper()}  ·  {format_model_size(item.size_bytes)}",
            portrait_size=THUMBNAIL_SIZE,
            selectable=False,
            parent=self,
        )
        if card.thumbnail is not None and image is None:
            self.portrait.set_thumbnail_unavailable()
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        self.remove_button = TransparentToolButton(FIF.DELETE, self.portrait)
        self.remove_button.setObjectName(f"OnboardingRemoveModel_{item.version_id}")
        self.remove_button.setProperty("onboardingCardRemove", True)
        self.remove_button.setFixedSize(28, 28)
        self.remove_button.setIconSize(QSize(18, 18))
        self.remove_button.setStyleSheet(_REMOVE_BUTTON_STYLE)
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.move(self.portrait.width() - 38, 10)
        accessible_name = render_application_text(
            app_text("Remove %1", item.display_name)
        )
        set_fluent_tooltip_text(self.remove_button, accessible_name)
        self.remove_button.setAccessibleName(accessible_name)
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(item.version_id)
        )
        self.remove_button.raise_()


def _card_image(card: RecommendationCardAsset) -> QImage | None:
    """Decode a retained exact-version thumbnail for checkout rendering."""

    if card.thumbnail is None:
        return None
    return thumbnail_image(card.thumbnail)
