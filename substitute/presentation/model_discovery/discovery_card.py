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

"""Render a provider-neutral suggestion card and its acquisition-source menu."""

from __future__ import annotations

from functools import partial

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF  # type: ignore[import-untyped]

from substitute.domain.model_metadata import ThumbnailAsset
from substitute.domain.model_suggestions import ModelSuggestion, ModelSuggestionAccess
from substitute.presentation.onboarding.onboarding_recommendation_geometry import (
    CARD_HEIGHT,
    CARD_WIDTH,
    THUMBNAIL_SIZE,
)
from substitute.presentation.onboarding.onboarding_recommendation_portrait import (
    RecommendationPortrait,
)
from substitute.presentation.resources.brand_icons import model_provider_badge_icon_path
from substitute.presentation.resources.fluent_app_icon import AppIcon
from substitute.presentation.widgets.civitai_page_action import UrlOpener
from substitute.presentation.widgets.menu_model import (
    MenuItem,
    MenuModel,
    MenuSeparator,
)
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.fluent_tooltips import set_fluent_tooltip_text
from sugarsubstitute_shared.presentation.localization import render_application_text


class ModelSuggestionCard(QFrame):
    """Render one provider-neutral, whole-card selectable model suggestion."""

    selection_changed = Signal(str, bool)
    provider_changed = Signal(str, str)

    def __init__(
        self, suggestion: ModelSuggestion, *, open_url: UrlOpener, parent: QWidget
    ) -> None:
        """Build a loading card with explicit provider access information."""

        super().__init__(parent)
        self._suggestion = suggestion
        offer = suggestion.primary_offer
        self._selected_provider_id = offer.reference.provider_id
        self._open_url = open_url
        self.setObjectName("ModelSuggestionCard")
        self.setProperty("selected", False)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        accessible_name = render_application_text(
            app_text("%1 model recommendation", suggestion.model_name)
        )
        self.portrait = RecommendationPortrait(
            image=None,
            title=suggestion.model_name,
            thumbnail_failed=offer.thumbnail_url is None,
            selected=False,
            accessible_name=accessible_name,
            portrait_size=THUMBNAIL_SIZE,
            parent=self,
        )
        self.portrait.selection_changed.connect(self._publish_selection)
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignCenter)
        self.link_button = QToolButton(self.portrait)
        self.link_button.setAutoRaise(True)
        self.link_button.setFixedSize(28, 28)
        self.link_button.setIconSize(QSize(20, 20))
        self.link_button.move(10, 10)
        self._refresh_provider_button()
        self.link_button.clicked.connect(self._open_selected_provider_page)
        self.key_indicator = QLabel(self.portrait)
        self.key_indicator.setObjectName("ModelSuggestionKeyIndicator")
        self.key_indicator.setPixmap(
            QIcon(AppIcon.KEY_20_REGULAR.path()).pixmap(QSize(16, 16))
        )
        self.key_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_indicator.setFixedSize(24, 24)
        self.key_indicator.move(40, 12)
        self.key_indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.key_indicator.setStyleSheet(
            "QLabel#ModelSuggestionKeyIndicator {"
            "background-color: rgba(20, 22, 28, 225);"
            "border: 1px solid rgba(255, 255, 255, 100);"
            "border-radius: 12px; }"
        )
        self._refresh_key_indicator()
        for surface in (self, self.portrait):
            surface.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            surface.customContextMenuRequested.connect(
                lambda position, owner=surface: self._show_provider_menu(
                    owner.mapToGlobal(position)
                )
            )

    def _refresh_key_indicator(self) -> None:
        """Identify protected offers without covering their thumbnails."""

        offer = self._suggestion.offer_for_provider(self._selected_provider_id)
        assert offer is not None
        explanation = render_application_text(
            app_text("%1 API key required", offer.reference.provider_name)
        )
        self.key_indicator.setAccessibleName(explanation)
        self.key_indicator.setVisible(
            offer.access is ModelSuggestionAccess.API_KEY_REQUIRED
        )

    @property
    def identity(self) -> str:
        """Return the exact provider-version identity represented by this card."""

        return self._suggestion.identity

    @property
    def selected_provider_id(self) -> str:
        """Return the provider selected to acquire this card's exact artifact."""

        return self._selected_provider_id

    def provider_menu_model(self) -> MenuModel:
        """Return provider links and explicit acquisition-source choices."""

        entries: list[MenuItem | MenuSeparator] = []
        for offer in self._suggestion.offers:
            provider_id = offer.reference.provider_id
            provider_name = offer.reference.provider_name
            entries.append(
                MenuItem(
                    f"model_provider.view.{provider_id}",
                    app_text(
                        "View %1 on %2",
                        self._suggestion.model_name,
                        provider_name,
                    ),
                    callback=partial(
                        self._open_provider_page,
                        offer.model_page_url,
                    ),
                    icon=_provider_icon(provider_id),
                )
            )
        if len(self._suggestion.offers) > 1:
            entries.append(MenuSeparator())
            for offer in self._suggestion.offers:
                provider_id = offer.reference.provider_id
                entries.append(
                    MenuItem(
                        f"model_provider.acquire.{provider_id}",
                        app_text("Download from %1", offer.reference.provider_name),
                        callback=partial(self._select_provider, provider_id),
                        checkable=True,
                        checked=provider_id == self._selected_provider_id,
                        icon=_provider_icon(provider_id),
                    )
                )
        return MenuModel(tuple(entries))

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

    def _select_provider(self, provider_id: str) -> None:
        """Select one reviewed acquisition offer and refresh its visible badge."""

        if self._suggestion.offer_for_provider(provider_id) is None:
            raise ValueError(f"Unknown model provider offer: {provider_id}")
        self._selected_provider_id = provider_id
        self._refresh_provider_button()
        self._refresh_key_indicator()
        self.provider_changed.emit(self.identity, provider_id)

    def _refresh_provider_button(self) -> None:
        """Project the selected acquisition provider onto the card badge."""

        offer = self._suggestion.offer_for_provider(self._selected_provider_id)
        assert offer is not None
        self.link_button.setIcon(_provider_icon(offer.reference.provider_id))
        tooltip = render_application_text(
            app_text(
                "View %1 on %2",
                self._suggestion.model_name,
                offer.reference.provider_name,
            )
        )
        set_fluent_tooltip_text(self.link_button, tooltip)

    def _open_selected_provider_page(self) -> None:
        """Open the model page owned by the selected acquisition provider."""

        offer = self._suggestion.offer_for_provider(self._selected_provider_id)
        assert offer is not None
        self._open_url(offer.model_page_url)

    def _open_provider_page(self, url: str) -> None:
        """Open one provider page while discarding transport-specific results."""

        self._open_url(url)

    def _show_provider_menu(self, global_position: object) -> None:
        """Show all exact provider links and acquisition routes for this card."""

        menu = QFluentMenuRenderer(parent=self).render(self.provider_menu_model())
        menu.exec(global_position)


def _provider_icon(provider_id: str) -> QIcon:
    """Return a provider brand icon or a neutral web fallback."""

    path = model_provider_badge_icon_path(provider_id)
    return QIcon(str(path)) if path is not None else FIF.GLOBE.icon()


__all__ = ["ModelSuggestionCard"]
