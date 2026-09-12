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

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    FluentIcon as FIF,
    IndeterminateProgressRing,
    PrimaryPushButton,
    PushButton,
    TransparentToolButton,
)

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import (
    ModelSuggestion,
    ModelSuggestionAccess,
    ModelSuggestionPlan,
)
from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedSubtitleLabel,
)
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import set_fluent_tooltip_text
from sugarsubstitute_shared.presentation.localization import render_application_text

_GRID_COLUMNS = 4


class ModelSuggestionCard(QFrame):
    """Render one provider-neutral, whole-card selectable model suggestion."""

    selection_changed = Signal(str, bool)

    def __init__(
        self, suggestion: ModelSuggestion, *, open_url: UrlOpener, parent: QWidget
    ) -> None:
        """Build a loading card with explicit provider access information."""

        super().__init__(parent)
        self._suggestion = suggestion
        self.setObjectName("ModelSuggestionCard")
        self.setProperty("selected", False)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        accessible_name = render_application_text(
            app_text("%1 model recommendation", suggestion.model_name)
        )
        metadata = (
            render_application_text(
                app_text(
                    "%1 API key required",
                    suggestion.reference.provider_name,
                )
            )
            if suggestion.access is ModelSuggestionAccess.API_KEY_REQUIRED
            else ""
        )
        self.portrait = RecommendationPortrait(
            pixmap=None,
            title=suggestion.model_name,
            thumbnail_failed=suggestion.thumbnail_url is None,
            selected=False,
            accessible_name=accessible_name,
            metadata=metadata,
            portrait_size=THUMBNAIL_SIZE,
            parent=self,
        )
        self.portrait.selection_changed.connect(self._publish_selection)
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        self.link_button = TransparentToolButton(self.portrait)
        self.link_button.setIcon(FIF.GLOBE)
        self.link_button.setFixedSize(28, 28)
        self.link_button.setIconSize(QSize(20, 20))
        self.link_button.move(10, 10)
        tooltip = render_application_text(
            app_text(
                "View %1 on %2",
                suggestion.model_name,
                suggestion.reference.provider_name,
            )
        )
        set_fluent_tooltip_text(self.link_button, tooltip)
        self.link_button.clicked.connect(lambda: open_url(suggestion.model_page_url))
        if metadata:
            self.access_label = LocalizedCaptionLabel(
                app_text("API key required"), self.portrait
            )
            self.access_label.setObjectName("ModelSuggestionAccessLabel")
            self.access_label.adjustSize()
            self.access_label.move(10, THUMBNAIL_SIZE.height() - 34)
            self.access_label.raise_()

    @property
    def identity(self) -> str:
        """Return the exact provider-version identity represented by this card."""

        return self._suggestion.identity

    def set_selected(self, selected: bool) -> None:
        """Project exclusive gallery selection onto the native card control."""

        self.portrait.set_selected(selected)

    def set_thumbnail(self, thumbnail: ThumbnailAsset) -> bool:
        """Install a decoded thumbnail into this card."""

        return self.portrait.set_thumbnail(thumbnail)

    def set_thumbnail_unavailable(self) -> None:
        """Settle this card after preview loading fails."""

        self.portrait.set_thumbnail_unavailable()

    def _publish_selection(self, selected: bool) -> None:
        """Publish one user-authored card selection."""

        self.selection_changed.emit(self.identity, selected)


class ModelDiscoveryModal(QDialog):
    """Show loading, provider suggestions, and in-place download progress."""

    download_requested = Signal(str)

    def __init__(
        self, *, open_url: UrlOpener | None = None, parent: QWidget | None = None
    ) -> None:
        """Build the reusable browse surface before provider work begins."""

        super().__init__(parent)
        self._open_url = open_url or open_external_url
        self._plan: ModelSuggestionPlan | None = None
        self._cards: dict[str, ModelSuggestionCard] = {}
        self._selected_identity: str | None = None
        self.setObjectName("ModelSuggestionModal")
        self.setWindowTitle(render_application_text(app_text("Find models")))
        self.setModal(True)
        self.resize(1040, 720)
        self._build()

    @property
    def selected_identity(self) -> str | None:
        """Return the exact explicitly selected provider version."""

        return self._selected_identity

    def show_loading(self) -> None:
        """Reveal the modal immediately while discovery runs."""

        self._clear_cards()
        self.status_label.setText(
            render_application_text(app_text("Finding compatible models…"))
        )
        self.loading_ring.start()
        self.loading_ring.show()
        self.download_button.setEnabled(False)
        self.open()

    def show_plan(self, plan: ModelSuggestionPlan) -> None:
        """Render provider-ranked suggestions without selecting one automatically."""

        self._plan = plan
        self._clear_cards()
        self.loading_ring.stop()
        self.loading_ring.hide()
        message = (
            app_text("Choose a model to download and use in this picker.")
            if plan.suggestions
            else app_text("No compatible model suggestions are available right now.")
        )
        self.status_label.setText(render_application_text(message))
        for index, suggestion in enumerate(plan.suggestions):
            card = ModelSuggestionCard(
                suggestion, open_url=self._open_url, parent=self.card_host
            )
            card.selection_changed.connect(self._select_exclusively)
            self.card_grid.addWidget(
                card, index // _GRID_COLUMNS, index % _GRID_COLUMNS
            )
            self._cards[suggestion.identity] = card
        self.browse_button.setVisible(bool(plan.browse_urls))
        self.download_button.setEnabled(False)

    def show_failure(self, message: str) -> None:
        """Keep a provider failure recoverable inside the open modal."""

        self.loading_ring.stop()
        self.loading_ring.hide()
        self.status_label.setText(message)
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
        layout.addWidget(LocalizedSubtitleLabel(app_text("Find a model"), self))
        description = LocalizedCaptionLabel(
            app_text(
                "These popular models are compatible with this picker. Nothing downloads until you choose one."
            ),
            self,
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        status_row = QHBoxLayout()
        self.loading_ring = IndeterminateProgressRing(self, start=False)
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
        self.download_button.setEnabled(self._selected_identity is not None)

    def _request_download(self) -> None:
        """Publish the explicit selection without closing the progress surface."""

        if self._selected_identity is not None:
            self.download_requested.emit(self._selected_identity)

    def _browse(self) -> None:
        """Open the first capable provider's compatibility-filtered browse page."""

        if self._plan is not None and self._plan.browse_urls:
            self._open_url(self._plan.browse_urls[0][1])


__all__ = ["ModelDiscoveryModal", "ModelSuggestionCard"]
