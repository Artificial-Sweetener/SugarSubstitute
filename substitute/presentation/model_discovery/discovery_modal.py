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

"""Present the reusable model-suggestion gallery for picker recovery."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    PrimaryPushButton,
    PushButton,
)

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionContext,
    ModelSuggestionPlan,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedSubtitleLabel,
)
from substitute.presentation.model_discovery.discovery_copy import discovery_copy
from substitute.presentation.model_discovery.discovery_card import ModelSuggestionCard
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.busy_ring import BusyRing
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import render_application_text

_GRID_COLUMNS = 4


class ModelDiscoveryModal(QDialog):
    """Show loading, provider suggestions, and in-place download progress."""

    download_requested = Signal(str, str)
    credential_requested = Signal(str, str)
    show_all_requested = Signal()

    def __init__(
        self, *, open_url: UrlOpener | None = None, parent: QWidget | None = None
    ) -> None:
        """Build the reusable browse surface before provider work begins."""

        super().__init__(parent)
        self._open_url = open_url or open_external_url
        self._plan: ModelSuggestionPlan | None = None
        self._cards: dict[str, ModelSuggestionCard] = {}
        self._credential_available: set[str] = set()
        self._public_only = False
        self._selected_identity: str | None = None
        self.setObjectName("ModelSuggestionModal")
        self.setWindowTitle(render_application_text(app_text("Download a model?")))
        self.setModal(True)
        self.resize(1040, 720)
        self._build()

    @property
    def selected_identity(self) -> str | None:
        """Return the exact explicitly selected provider version."""

        return self._selected_identity

    def set_context(self, context: ModelSuggestionContext) -> None:
        """Name the requested model role before loading or showing its offers."""

        title, explanation = discovery_copy(context)
        self.title_label.setText(title)
        self.description_label.setText(explanation)
        self.setWindowTitle(render_application_text(title))

    def show_loading(self) -> None:
        """Reveal the modal immediately while discovery runs."""

        self._selected_identity = None
        for card in self._cards.values():
            card.set_selected(False)
            card.setEnabled(True)
        self.card_host.hide()
        self.browse_button.hide()
        self.show_all_button.hide()
        self.status_label.setText(
            render_application_text(app_text("Finding compatible models…"))
        )
        self.status_label.show()
        self.loading_ring.start()
        self.loading_ring.show()
        self.cancel_button.setEnabled(True)
        self.download_button.setEnabled(False)
        self.show()

    def show_plan(
        self, plan: ModelSuggestionPlan, *, public_only: bool = False
    ) -> None:
        """Render provider-ranked suggestions without selecting one automatically."""

        self.set_context(plan.context)
        self._public_only = public_only
        identities = tuple(suggestion.identity for suggestion in plan.suggestions)
        reuse_cards = self._plan == plan and tuple(self._cards) == identities
        if reuse_cards:
            self._selected_identity = None
            for card in self._cards.values():
                card.set_selected(False)
                card.setEnabled(True)
        else:
            self._clear_cards()
            for index, suggestion in enumerate(plan.suggestions):
                card = ModelSuggestionCard(
                    suggestion, open_url=self._open_url, parent=self.card_host
                )
                card.selection_changed.connect(self._select_exclusively)
                card.provider_changed.connect(self._provider_changed)
                self.card_grid.addWidget(
                    card, index // _GRID_COLUMNS, index % _GRID_COLUMNS
                )
                self._cards[suggestion.identity] = card
        self._plan = plan
        self.loading_ring.stop()
        self.loading_ring.hide()
        if plan.suggestions:
            self.status_label.hide()
        else:
            self.status_label.setText(
                render_application_text(
                    app_text(
                        "No models that can be downloaded without a key are available right now."
                    )
                    if public_only
                    else app_text("No compatible models are available right now.")
                )
            )
            self.status_label.show()
        self.card_host.setVisible(bool(plan.suggestions))
        self.browse_button.setVisible(bool(plan.browse_urls))
        self.show_all_button.setVisible(public_only)
        self._refresh_primary_action()

    def set_provider_credential_available(
        self, provider_id: str, *, available: bool = True
    ) -> None:
        """Keep the footer aligned with the current secure-store state."""

        if available:
            self._credential_available.add(provider_id)
        else:
            self._credential_available.discard(provider_id)
        self._refresh_primary_action()

    def show_failure(self, message: str) -> None:
        """Keep a provider failure recoverable inside the open modal."""

        self.loading_ring.stop()
        self.loading_ring.hide()
        self.status_label.setText(message)
        self.status_label.show()
        self.cancel_button.setEnabled(True)
        for card in self._cards.values():
            card.setEnabled(True)
        self.download_button.setEnabled(self._selected_identity is not None)

    def set_thumbnail(self, identity: str, thumbnail: ThumbnailAsset) -> bool:
        """Install one asynchronously fetched thumbnail when still visible."""

        card = self._cards.get(identity)
        return card.set_thumbnail(thumbnail) if card is not None else False

    def set_thumbnail_unavailable(self, identity: str) -> bool:
        """Settle one card whose provider thumbnail failed."""

        card = self._cards.get(identity)
        if card is None:
            return False
        card.set_thumbnail_unavailable()
        return True

    def set_downloading(self, suggestion: ModelSuggestion) -> None:
        """Lock the reviewed choice while its verified transfer runs."""

        self.status_label.setText(
            render_application_text(
                app_text("Downloading and verifying %1…", suggestion.model_name)
            )
        )
        self.status_label.show()
        self.loading_ring.start()
        self.loading_ring.show()
        self.download_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        for card in self._cards.values():
            card.setEnabled(False)

    def finish_download(self) -> None:
        """Accept the modal after the installed value has been published."""

        self.loading_ring.stop()
        self.accept()

    def _build(self) -> None:
        """Compose the reusable gallery and stable action row."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)
        title, explanation = discovery_copy(None)
        self.title_label = LocalizedSubtitleLabel(title, self)
        layout.addWidget(self.title_label)
        self.description_label = LocalizedCaptionLabel(explanation, self)
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)
        status_row = QHBoxLayout()
        self.loading_ring = BusyRing(self, start=False)
        self.loading_ring.setFixedSize(24, 24)
        self.status_label = LocalizedBodyLabel("", self)
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.loading_ring)
        status_row.addWidget(self.status_label, 1)
        layout.addLayout(status_row)
        self.card_host = QWidget(self)
        self.card_grid = QGridLayout(self.card_host)
        self.card_grid.setContentsMargins(0, 0, 0, 0)
        self.card_grid.setSpacing(10)
        layout.addWidget(self.card_host, 1)
        footer = QHBoxLayout()
        self.browse_button = PushButton(
            render_application_text(app_text("Explore more")), self
        )
        self.browse_button.setIcon(FIF.GLOBE)
        self.browse_button.clicked.connect(self._browse)
        footer.addWidget(self.browse_button)
        self.show_all_button = PushButton(
            render_application_text(app_text("Show all models")), self
        )
        self.show_all_button.clicked.connect(self.show_all_requested)
        self.show_all_button.hide()
        footer.addWidget(self.show_all_button)
        footer.addStretch(1)
        self.cancel_button = PushButton(
            render_application_text(app_text("Not now")), self
        )
        self.cancel_button.clicked.connect(self.reject)
        self.download_button = PrimaryPushButton(
            render_application_text(app_text("Download and use")), self
        )
        self.download_button.setIcon(FIF.DOWNLOAD)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._request_download)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.download_button)
        layout.addLayout(footer)

    def _clear_cards(self) -> None:
        """Remove prior provider cards and selection state."""

        while self.card_grid.count():
            item = self.card_grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self._cards.clear()
        self._selected_identity = None

    def _select_exclusively(self, identity: str, selected: bool) -> None:
        """Keep one picker recovery choice selected at a time."""

        if selected:
            self._selected_identity = identity
            for card_identity, card in self._cards.items():
                if card_identity != identity:
                    card.set_selected(False)
        elif self._selected_identity == identity:
            self._selected_identity = None
        self._refresh_primary_action()

    def _provider_changed(self, identity: str, _provider_id: str) -> None:
        """Refresh the footer when the selected card changes acquisition source."""

        if self._selected_identity == identity:
            self._refresh_primary_action()

    def _refresh_primary_action(self) -> None:
        """Put credential entry in the footer only for a selected locked offer."""

        identity = self._selected_identity
        card = self._cards.get(identity) if identity is not None else None
        suggestion = (
            next(
                (item for item in self._plan.suggestions if item.identity == identity),
                None,
            )
            if self._plan is not None and card is not None
            else None
        )
        offer = (
            suggestion.offer_for_provider(card.selected_provider_id)
            if suggestion is not None and card is not None
            else None
        )
        needs_key = (
            offer is not None
            and offer.access is ModelSuggestionAccess.API_KEY_REQUIRED
            and offer.reference.provider_id not in self._credential_available
        )
        if needs_key and offer is not None:
            self.download_button.setText(
                render_application_text(
                    app_text("Add %1 key", offer.reference.provider_name)
                )
            )
            self.download_button.setIcon(AppIcon.KEY_20_REGULAR)
        else:
            self.download_button.setText(
                render_application_text(app_text("Download and use"))
            )
            self.download_button.setIcon(FIF.DOWNLOAD)
        self.download_button.setEnabled(identity is not None)

    def _request_download(self) -> None:
        """Publish the explicit selection without closing the progress surface."""

        if self._selected_identity is not None:
            card = self._cards[self._selected_identity]
            suggestion = (
                next(
                    (
                        item
                        for item in self._plan.suggestions
                        if item.identity == self._selected_identity
                    ),
                    None,
                )
                if self._plan is not None
                else None
            )
            offer = (
                suggestion.offer_for_provider(card.selected_provider_id)
                if suggestion is not None
                else None
            )
            if (
                offer is not None
                and offer.access is ModelSuggestionAccess.API_KEY_REQUIRED
                and offer.reference.provider_id not in self._credential_available
            ):
                self.credential_requested.emit(
                    self._selected_identity, card.selected_provider_id
                )
            else:
                self.download_requested.emit(
                    self._selected_identity, card.selected_provider_id
                )

    def _browse(self) -> None:
        """Open the first capable provider's compatibility-filtered browse page."""

        if self._plan is not None and self._plan.browse_urls:
            self._open_url(self._plan.browse_urls[0][1])


__all__ = ["ModelDiscoveryModal"]
