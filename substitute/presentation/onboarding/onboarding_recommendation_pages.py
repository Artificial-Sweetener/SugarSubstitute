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

"""Render portrait model recommendations and exact download review."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IndeterminateProgressRing,
)

from sugarsubstitute_shared.localization import ApplicationText, app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    render_application_text,
)

from substitute.application.model_recommendations import (
    FamilyRecommendationPage,
    RecommendationCardAsset,
    model_family_presentation,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedCheckBox,
    LocalizedPushButton,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_loading import (
    RecommendationLoadingGallery,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
    thumbnail_pixmap,
)


class RecommendationCard(QFrame):
    """Render one selectable portrait recommendation with compact metadata."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)

    def __init__(
        self,
        card: RecommendationCardAsset,
        *,
        selected: bool,
        parent: QWidget,
    ) -> None:
        """Build an accessible card from provider-safe text and decoded media."""

        super().__init__(parent)
        recommendation = card.recommendation
        self._version_id = recommendation.version_id
        self.setObjectName("OnboardingRecommendationCard")
        self.setProperty("selected", selected)
        accessible_name = render_application_text(
            app_text("%1 model recommendation", recommendation.model_name)
        )
        self.setAccessibleName(accessible_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)
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
            parent=self,
        )
        self.checkbox = self.portrait.checkbox
        self.checkbox.setObjectName(
            f"OnboardingRecommendationSelect_{recommendation.version_id}"
        )
        self.portrait.selection_changed.connect(self._set_selected)
        layout.addWidget(self.portrait)
        self.link_button = LocalizedPushButton(app_text("View on CivitAI"), self)
        self.link_button.setObjectName(
            f"OnboardingRecommendationLink_{recommendation.version_id}"
        )
        self.link_button.setAccessibleName(
            render_application_text(
                app_text("View %1 on CivitAI", recommendation.model_name)
            )
        )
        self.link_button.clicked.connect(
            lambda: self.link_requested.emit(recommendation.model_page_url)
        )
        layout.addWidget(self.link_button)

    def set_thumbnail(self, thumbnail: ThumbnailAsset) -> bool:
        """Install one completed image into this card's portrait."""

        return self.portrait.set_thumbnail(thumbnail)

    def set_thumbnail_unavailable(self) -> None:
        """Settle this card's image area when loading fails."""

        self.portrait.set_thumbnail_unavailable()

    def set_selected(self, selected: bool) -> None:
        """Project an externally coordinated exclusive choice onto the portrait."""

        self.portrait.set_selected(selected)

    def _set_selected(self, selected: bool) -> None:
        """Project selection onto the card frame and notify the presenter."""

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self.selection_changed.emit(self._version_id, selected)


class ModelRecommendationPage(OnboardingPageFrame):
    """Show three large portrait recommendations for one missing family."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)
    own_model_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build recommendations and one coherent no-download selection."""

        super().__init__(
            title=app_text("Popular models this month"),
            description=app_text(
                "Choose a recommended model or tell Substitute that you will provide your own."
            ),
            icon=FIF.PHOTO,
            parent=parent,
        )
        self.setObjectName("OnboardingModelRecommendationPage")
        self._family_id: ModelFamilyId | None = None
        self._cards_by_version_id: dict[int, RecommendationCard] = {}
        self.family_label = LocalizedBodyLabel("", self)
        self.family_label.setObjectName("OnboardingRecommendationFamily")
        self.body_layout.addWidget(self.family_label)
        self.card_host = QWidget(self)
        self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(0, 0, 0, 0)
        self.card_grid.setHorizontalSpacing(14)
        self._loading_gallery = RecommendationLoadingGallery(
            host=self.card_host,
            grid=self.card_grid,
        )
        self.body_layout.addWidget(self.card_host)
        self.loading_row = QWidget(self)
        loading_layout = QHBoxLayout(self.loading_row)
        loading_layout.setContentsMargins(0, 18, 0, 18)
        loading_layout.setSpacing(12)
        self.loading_ring = IndeterminateProgressRing(self.loading_row, start=False)
        self.loading_ring.setFixedSize(26, 26)
        self.loading_ring.setAccessibleName(
            render_application_text(app_text("Loading recommendations…"))
        )
        self.loading_status = LocalizedBodyLabel("", self.loading_row)
        self.loading_status.setWordWrap(True)
        loading_layout.addWidget(self.loading_ring)
        loading_layout.addWidget(self.loading_status, 1)
        self.loading_row.hide()
        self.body_layout.addWidget(self.loading_row)
        self.empty_label = LocalizedCaptionLabel(
            app_text(
                "CivitAI did not return a safe portrait for this family. You can skip it or find your own models."
            ),
            self,
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.body_layout.addWidget(self.empty_label)
        self.own_model_choice = QFrame(self)
        self.own_model_choice.setObjectName("OnboardingRecommendationAlternative")
        self.own_model_choice.setProperty("selected", False)
        own_model_layout = QVBoxLayout(self.own_model_choice)
        own_model_layout.setContentsMargins(16, 12, 16, 12)
        own_model_layout.setSpacing(4)
        self.own_model_checkbox = LocalizedCheckBox("", self.own_model_choice)
        self.own_model_checkbox.setObjectName("OnboardingOwnModelChoice")
        own_model_layout.addWidget(self.own_model_checkbox)
        own_model_helper = LocalizedCaptionLabel(
            app_text("Continue without downloading a model for this family."),
            self.own_model_choice,
        )
        own_model_helper.setObjectName("OnboardingFieldHelper")
        own_model_layout.addWidget(own_model_helper)
        self.body_layout.addWidget(self.own_model_choice)
        self.own_model_checkbox.toggled.connect(self._set_own_model_selected)

    def show_loading(self, family_id: ModelFamilyId) -> None:
        """Show the final three-card composition while CivitAI responds."""

        self._clear_cards()
        self._set_family(family_id)
        self._loading_gallery.build()
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        self.empty_label.hide()
        self.own_model_choice.hide()

    def show_failure(
        self,
        family_id: ModelFamilyId,
        message: ApplicationText,
    ) -> None:
        """Keep provider failure on the page where the user can recover."""

        self._clear_cards()
        self._set_family(family_id)
        self.loading_ring.stop()
        self.loading_ring.hide()
        apply_application_text(self.loading_status, message)
        self.loading_row.show()
        self.card_host.hide()
        self.empty_label.hide()
        self.own_model_choice.hide()

    def current_family(self) -> ModelFamilyId | None:
        """Return the family currently represented by the card grid."""

        return self._family_id

    def visible_cards(self) -> tuple[RecommendationCard, ...]:
        """Return the currently rendered cards for qualification and accessibility."""

        return tuple(self._cards_by_version_id.values())

    def set_recommendations(
        self,
        page: FamilyRecommendationPage,
        *,
        selected_version_ids: frozenset[int],
        use_own_model: bool,
    ) -> None:
        """Replace cards with one missing-family page and retained selections."""

        self._clear_cards()
        self._set_family(page.family_id)
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        self.own_model_choice.show()
        self.own_model_checkbox.blockSignals(True)
        self.own_model_checkbox.setChecked(use_own_model)
        self.own_model_checkbox.blockSignals(False)
        self._style_own_model_choice(use_own_model)
        rendered = 0
        for index, card in enumerate(page.cards[:3]):
            widget = RecommendationCard(
                card,
                selected=card.recommendation.version_id in selected_version_ids,
                parent=self.card_host,
            )
            widget.selection_changed.connect(self.selection_changed)
            widget.link_requested.connect(self.link_requested)
            self.card_grid.addWidget(widget, 0, index)
            self._cards_by_version_id[card.recommendation.version_id] = widget
            rendered += 1
        self.empty_label.setVisible(rendered == 0)

    def _clear_cards(self) -> None:
        """Remove prior cards before showing another family state."""

        self._loading_gallery.clear()
        _clear_layout(self.card_grid)
        self.card_host.setMinimumHeight(0)
        self._cards_by_version_id.clear()

    def _set_family(self, family_id: ModelFamilyId) -> None:
        """Render the family heading and corresponding no-download choice."""

        self._family_id = family_id
        presentation = model_family_presentation(family_id)
        if family_id is ModelFamilyId.SDXL:
            self.family_label.setText(app_text("Illustrious · SDXL compatible"))
        else:
            self.family_label.setText(presentation.name)
        apply_application_text(
            self.own_model_checkbox,
            app_text("I'll provide my own %1 model", presentation.name),
        )

    def clear_model_selections(self) -> None:
        """Clear visible download cards after choosing the exclusive alternative."""

        for card in self._cards_by_version_id.values():
            card.set_selected(False)

    def clear_own_model_choice(self) -> None:
        """Clear the exclusive alternative after choosing a download card."""

        self.own_model_checkbox.blockSignals(True)
        self.own_model_checkbox.setChecked(False)
        self.own_model_checkbox.blockSignals(False)
        self._style_own_model_choice(False)

    def _set_own_model_selected(self, selected: bool) -> None:
        """Style and publish the inline no-download selection."""

        self._style_own_model_choice(selected)
        self.own_model_changed.emit(selected)

    def _style_own_model_choice(self, selected: bool) -> None:
        """Refresh the alternative card's explicit selected treatment."""

        self.own_model_choice.setProperty("selected", selected)
        self.own_model_choice.style().unpolish(self.own_model_choice)
        self.own_model_choice.style().polish(self.own_model_choice)

    def set_thumbnail(self, version_id: int, thumbnail: ThumbnailAsset) -> bool:
        """Install a completed thumbnail when its card is currently visible."""

        card = self._cards_by_version_id.get(version_id)
        return card.set_thumbnail(thumbnail) if card is not None else False

    def set_thumbnail_unavailable(self, version_id: int) -> bool:
        """Settle one visible card whose thumbnail request failed."""

        card = self._cards_by_version_id.get(version_id)
        if card is None:
            return False
        card.set_thumbnail_unavailable()
        return True


def _clear_layout(layout: QGridLayout) -> None:
    """Delete every prior recommendation card before rendering another family."""

    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
