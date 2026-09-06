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

"""Render the reusable ten-choice model-family recommendation page."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget
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
    RecommendationLinkResult,
    model_family_presentation,
)
from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
)
from substitute.presentation.onboarding.onboarding_model_link_import import (
    ModelLinkImportOverlay,
)
from substitute.presentation.onboarding.onboarding_page_primitives import (
    OnboardingPageFrame,
)
from substitute.presentation.onboarding.onboarding_recommendation_cards import (
    RecommendationActionCard,
    RecommendationCard,
    civitai_action_card,
    unavailable_recommendation_card,
)
from substitute.presentation.onboarding.onboarding_recommendation_loading import (
    RecommendationLoadingGallery,
)

_CURATED_CARD_COUNT = 8
_GRID_COLUMNS = 5


class ModelRecommendationPage(OnboardingPageFrame):
    """Show eight curated models and two coherent family choices in a 5×2 grid."""

    selection_changed = Signal(int, bool)
    link_requested = Signal(str)
    own_model_changed = Signal(bool)
    model_links_requested = Signal(object, tuple)
    imported_models_accepted = Signal(tuple)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the stable family picker and its contained import workflow."""

        super().__init__(
            title=app_text("Choose models"),
            description=app_text(
                "Choose a model to download, explore CivitAI, or bring your own."
            ),
            icon=FIF.PHOTO,
            parent=parent,
        )
        self.content_column.setMinimumWidth(1068)
        self.content_column.setMaximumWidth(1068)
        self.setObjectName("OnboardingModelRecommendationPage")
        self._family_id: ModelFamilyId | None = None
        self._current_page: FamilyRecommendationPage | None = None
        self._cards_by_version_id: dict[int, RecommendationCard] = {}
        self._import_overlay: ModelLinkImportOverlay | None = None
        self.card_host = QWidget(self)
        self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(0, 0, 0, 0)
        self.card_grid.setHorizontalSpacing(10)
        self.card_grid.setVerticalSpacing(10)
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
                "CivitAI did not return enough safe previews. You can still browse CivitAI or bring your own model."
            ),
            self,
        )
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.body_layout.addWidget(self.empty_label)

    def show_loading(self, family_id: ModelFamilyId) -> None:
        """Show the final ten-card composition while CivitAI responds."""

        self._clear_cards()
        self._set_family(family_id)
        self._loading_gallery.build()
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        self.empty_label.hide()

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

    def current_family(self) -> ModelFamilyId | None:
        """Return the family currently represented by the card grid."""

        return self._family_id

    def visible_cards(self) -> tuple[RecommendationCard, ...]:
        """Return currently rendered curated cards for qualification."""

        return tuple(self._cards_by_version_id.values())

    def set_recommendations(
        self,
        page: FamilyRecommendationPage,
        *,
        selected_version_ids: frozenset[int],
        use_own_model: bool,
    ) -> None:
        """Render one family as eight curated and two reusable special cards."""

        self._clear_cards()
        self._current_page = page
        self._set_family(page.family_id)
        self.loading_ring.stop()
        self.loading_row.hide()
        self.card_host.show()
        for index, card in enumerate(page.cards[:_CURATED_CARD_COUNT]):
            widget = RecommendationCard(
                card,
                selected=card.recommendation.version_id in selected_version_ids,
                parent=self.card_host,
            )
            widget.selection_changed.connect(self.selection_changed)
            widget.link_requested.connect(self.link_requested)
            self._add_grid_widget(widget, index)
            self._cards_by_version_id[card.recommendation.version_id] = widget
        for index in range(len(page.cards), _CURATED_CARD_COUNT):
            self._add_grid_widget(
                unavailable_recommendation_card(parent=self.card_host),
                index,
            )
        self.import_card = civitai_action_card(parent=self.card_host)
        self.import_card.activated.connect(self._open_import_overlay)
        self._set_import_card_copy(page.imported_cards)
        self._add_grid_widget(self.import_card, 8)
        self.own_model_card = RecommendationActionCard(
            title=app_text("No thanks,\nI’ll bring my own"),
            helper="",
            icon=FIF.FOLDER,
            object_name="OnboardingOwnModelChoice",
            parent=self.card_host,
        )
        self.own_model_card.set_selected(use_own_model)
        self.own_model_card.activated.connect(
            lambda: self._set_own_model_selected(
                not bool(self.own_model_card.property("selected"))
            )
        )
        self._add_grid_widget(self.own_model_card, 9)
        self.empty_label.setVisible(len(page.cards) < _CURATED_CARD_COUNT)

    def show_import_results(
        self, results: tuple[RecommendationLinkResult, ...]
    ) -> None:
        """Project asynchronous link validation into the contained overlay."""

        if self._import_overlay is not None:
            self._import_overlay.set_results(results)

    def clear_model_selections(self) -> None:
        """Clear visible curated choices after choosing the exclusive alternative."""

        for card in self._cards_by_version_id.values():
            card.set_selected(False)

    def clear_own_model_choice(self) -> None:
        """Clear the exclusive alternative after choosing any downloadable model."""

        if hasattr(self, "own_model_card"):
            self.own_model_card.set_selected(False)

    def set_thumbnail(self, version_id: int, thumbnail: ThumbnailAsset) -> bool:
        """Install a completed thumbnail when its curated card is visible."""

        card = self._cards_by_version_id.get(version_id)
        return card.set_thumbnail(thumbnail) if card is not None else False

    def set_thumbnail_unavailable(self, version_id: int) -> bool:
        """Settle one visible card whose thumbnail request failed."""

        card = self._cards_by_version_id.get(version_id)
        if card is None:
            return False
        card.set_thumbnail_unavailable()
        return True

    def _add_grid_widget(self, widget: QWidget, index: int) -> None:
        """Place one equal-size choice in the stable centered 5×2 grid."""

        self.card_grid.addWidget(widget, index // _GRID_COLUMNS, index % _GRID_COLUMNS)

    def _clear_cards(self) -> None:
        """Remove prior cards before showing another family state."""

        self._loading_gallery.clear()
        while self.card_grid.count():
            item = self.card_grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.card_host.setMinimumHeight(0)
        self._cards_by_version_id.clear()

    def _set_family(self, family_id: ModelFamilyId) -> None:
        """Put catalog-owned family identity in the page title."""

        self._family_id = family_id
        presentation = model_family_presentation(family_id)
        apply_application_text(
            self.hero_panel.title_label,
            app_text("Popular %1 models", presentation.recommendation_name),
        )

    def _set_own_model_selected(self, selected: bool) -> None:
        """Style and publish the exclusive bring-your-own choice."""

        self.own_model_card.set_selected(selected)
        self.own_model_changed.emit(selected)

    def _open_import_overlay(self) -> None:
        """Open the link workflow as a child overlay of the installer window."""

        page = self._current_page
        if page is None:
            return
        window_host = self.window()
        styled_root = window_host.findChild(QWidget, "OnboardingRoot")
        host = styled_root if styled_root is not None else window_host
        if self._import_overlay is None or self._import_overlay.parent() is not host:
            self._import_overlay = ModelLinkImportOverlay(host=host)
            self._import_overlay.validation_requested.connect(
                self.model_links_requested
            )
            self._import_overlay.models_accepted.connect(self.imported_models_accepted)
            self._import_overlay.browse_requested.connect(self.link_requested)
        self._import_overlay.open_for(
            page.family_id,
            model_family_presentation(page.family_id),
            page.imported_cards,
        )

    def _set_import_card_copy(self, cards: tuple[RecommendationCardAsset, ...]) -> None:
        """Summarize retained imported models on the ninth card."""

        if cards:
            self.import_card.set_copy(
                (
                    app_text("1 model added")
                    if len(cards) == 1
                    else app_text("%1 models added", len(cards))
                ),
                app_text("Review or add more CivitAI links."),
            )
        self.import_card.set_previews(cards)


__all__ = ["ModelRecommendationPage"]
