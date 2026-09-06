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

"""Render compact reusable choices for model-family recommendations."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IconWidget,
    TransparentToolButton,
)

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    set_fluent_tooltip_text,
)
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)

from substitute.application.model_recommendations import RecommendationCardAsset
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.presentation.localization import (
    LocalizedCaptionLabel,
    LocalizedStrongBodyLabel,
)
from substitute.presentation.resources.brand_icons import civitai_badge_icon_path
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
    thumbnail_pixmap,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)


class RecommendationCard(QFrame):
    """Render one whole-card selectable model with an unobtrusive provider link."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)

    def __init__(
        self,
        card: RecommendationCardAsset,
        *,
        selected: bool,
        parent: QWidget,
    ) -> None:
        """Build one compact card from provider-safe text and decoded media."""

        super().__init__(parent)
        recommendation = card.recommendation
        self._version_id = recommendation.version_id
        self.setObjectName("OnboardingRecommendationCard")
        self.setProperty("selected", selected)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        accessible_name = render_application_text(
            app_text("%1 model recommendation", recommendation.model_name)
        )
        self.setAccessibleName(accessible_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        pixmap = (
            thumbnail_pixmap(card.thumbnail) if card.thumbnail is not None else None
        )
        self.portrait = RecommendationPortrait(
            pixmap=pixmap,
            title=recommendation.model_name,
            thumbnail_failed=card.thumbnail_failed
            or (card.thumbnail is not None and pixmap is None),
            selected=selected,
            accessible_name=accessible_name,
            portrait_size=THUMBNAIL_SIZE,
            parent=self,
        )
        self.checkbox = self.portrait.checkbox
        self.checkbox.setObjectName(
            f"OnboardingRecommendationSelect_{recommendation.version_id}"
        )
        self.portrait.selection_changed.connect(self._set_selected)
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        self.link_button = TransparentToolButton(
            QIcon(str(civitai_badge_icon_path())), self.portrait
        )
        self.link_button.setObjectName(
            f"OnboardingRecommendationLink_{recommendation.version_id}"
        )
        self.link_button.setProperty("onboardingProviderAction", True)
        self.link_button.setFixedSize(28, 28)
        self.link_button.setIconSize(QSize(20, 20))
        self.link_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_button.move(10, 10)
        link_tooltip = render_application_text(
            app_text("View %1 on CivitAI", recommendation.model_name)
        )
        set_fluent_tooltip_text(self.link_button, link_tooltip)
        self.link_button.setAccessibleName(link_tooltip)
        self.link_button.clicked.connect(
            lambda: self.link_requested.emit(recommendation.model_page_url)
        )
        self.link_button.raise_()

    def set_thumbnail(self, thumbnail: ThumbnailAsset) -> bool:
        """Install one completed image into this card's centered thumbnail."""

        return self.portrait.set_thumbnail(thumbnail)

    def set_thumbnail_unavailable(self) -> None:
        """Settle this card's image area when loading fails."""

        self.portrait.set_thumbnail_unavailable()

    def set_selected(self, selected: bool) -> None:
        """Project externally coordinated selection onto the card."""

        self.portrait.set_selected(selected)

    def _set_selected(self, selected: bool) -> None:
        """Refresh selected treatment and notify the presenter."""

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.selection_changed.emit(self._version_id, selected)


class RecommendationActionCard(QFrame):
    """Render one equal-size action or exclusive alternative inside the grid."""

    activated = Signal()

    def __init__(
        self,
        *,
        title: ApplicationText,
        helper: ApplicationText,
        icon: object,
        object_name: str,
        parent: QWidget,
    ) -> None:
        """Build a keyboard-operable card with centered content."""

        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("selected", False)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)
        layout.addStretch(1)
        self.icon = IconWidget(icon, self)
        self.icon.setFixedSize(28, 28)
        layout.addWidget(self.icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.preview_mosaic = RecommendationPreviewMosaic(self)
        self.preview_mosaic.hide()
        layout.addWidget(
            self.preview_mosaic,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        self.title_label = LocalizedStrongBodyLabel(title, self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.helper_label = LocalizedCaptionLabel(helper, self)
        self.helper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.helper_label.setWordWrap(True)
        layout.addWidget(self.helper_label)
        self.helper_label.setVisible(bool(self.helper_label.text()))
        layout.addStretch(1)

    def set_copy(self, title: ApplicationText, helper: ApplicationText) -> None:
        """Replace family- or count-specific text without rebuilding the grid."""

        apply_application_text(self.title_label, title)
        apply_application_text(self.helper_label, helper)
        self.helper_label.setVisible(bool(self.helper_label.text()))

    def set_selected(self, selected: bool) -> None:
        """Refresh the explicit exclusive-choice treatment."""

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def set_previews(self, cards: tuple[RecommendationCardAsset, ...]) -> None:
        """Replace the action icon with a compact centered accepted-model mosaic."""

        self.preview_mosaic.set_cards(cards)
        has_previews = bool(cards)
        self.preview_mosaic.setVisible(has_previews)
        self.icon.setVisible(not has_previews)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Activate the whole card with the primary pointer button."""

        if event.button() is Qt.MouseButton.LeftButton:
            self.activated.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Activate the card with Space or Enter."""

        if event.key() in {Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class RecommendationPreviewMosaic(QWidget):
    """Render up to four accepted thumbnails inside one action card."""

    def __init__(self, parent: QWidget) -> None:
        """Build a fixed two-by-two preview surface."""

        super().__init__(parent)
        self.setObjectName("OnboardingRecommendationPreviewMosaic")
        self.setFixedSize(60, 40)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(2)

    def set_cards(self, cards: tuple[RecommendationCardAsset, ...]) -> None:
        """Render the first four usable accepted thumbnails in stable order."""

        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for index, card in enumerate(cards[:4]):
            label = QLabel(self)
            label.setObjectName("OnboardingRecommendationMosaicImage")
            label.setFixedSize(29, 19)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = (
                thumbnail_pixmap(card.thumbnail) if card.thumbnail is not None else None
            )
            if pixmap is not None:
                label.setPixmap(
                    pixmap.scaled(
                        label.size(),
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._grid.addWidget(label, index // 2, index % 2)


def civitai_action_card(*, parent: QWidget) -> RecommendationActionCard:
    """Return the reusable card that opens the contained CivitAI link workflow."""

    return RecommendationActionCard(
        title=app_text("Choose from CivitAI"),
        helper=app_text("Paste and preview model links."),
        icon=QIcon(str(civitai_badge_icon_path())),
        object_name="OnboardingCivitaiImportCard",
        parent=parent,
    )


def unavailable_recommendation_card(*, parent: QWidget) -> RecommendationActionCard:
    """Return a disabled placeholder that preserves the ten-card composition."""

    card = RecommendationActionCard(
        title=app_text("Preview unavailable"),
        helper="",
        icon=FIF.PHOTO,
        object_name="OnboardingUnavailableRecommendationCard",
        parent=parent,
    )
    card.setEnabled(False)
    card.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    card.setCursor(Qt.CursorShape.ArrowCursor)
    return card


__all__ = [
    "CARD_HEIGHT",
    "CARD_WIDTH",
    "RecommendationActionCard",
    "RecommendationCard",
    "THUMBNAIL_SIZE",
    "civitai_action_card",
    "unavailable_recommendation_card",
]
