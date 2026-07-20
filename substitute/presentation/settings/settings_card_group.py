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

"""Group related Settings cards under a compact Fluent section header."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from qfluentwidgets import CaptionLabel, StrongBodyLabel  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_GROUP_SPACING,
    SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN,
)
from sugarsubstitute_shared.presentation.localization import (
    ApplicationMessage,
    ApplicationText,
    LocalizationBindings,
    apply_application_text,
)


class SettingsCardGroup(QWidget):
    """Own one Settings section title and its vertical stack of cards."""

    def __init__(
        self,
        title: ApplicationText,
        *,
        subtitle: ApplicationText = "",
        cards: Iterable[QWidget] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Create a group with optional initial cards."""

        super().__init__(parent)
        stable_title = (
            title.source_text if isinstance(title, ApplicationMessage) else title
        )
        self.setObjectName(f"SettingsCardGroup-{stable_title.replace(' ', '')}")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.title_label = StrongBodyLabel(title, self)
        self.subtitle_label = CaptionLabel(subtitle, self)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        self._localization_bindings = LocalizationBindings(self)
        self._bind_heading_messages(title, subtitle)
        self._cards: list[QWidget] = []
        self._build_layout()
        for card in cards:
            self.add_card(card)

    def add_card(self, card: QWidget) -> None:
        """Append one Settings card to the group."""

        self._cards.append(card)
        self._card_layout.addWidget(card)

    def set_heading(
        self,
        title: ApplicationText,
        subtitle: ApplicationText = "",
    ) -> None:
        """Update the visible heading text for this Settings section."""

        apply_application_text(self.title_label, title)
        apply_application_text(self.subtitle_label, subtitle)
        self.subtitle_label.setVisible(bool(subtitle))

    def _bind_heading_messages(
        self,
        title: ApplicationText,
        subtitle: ApplicationText,
    ) -> None:
        """Retain marked heading copy while leaving opaque strings untouched."""

        if isinstance(title, ApplicationMessage):
            self._localization_bindings.bind_message(self.title_label, title)
        if isinstance(subtitle, ApplicationMessage):
            self._localization_bindings.bind_message(self.subtitle_label, subtitle)

    def set_cards(self, cards: Iterable[QWidget]) -> None:
        """Replace the card order while preserving reused card widgets."""

        next_cards = list(cards)
        removed_cards = [card for card in self._cards if card not in next_cards]
        for card in self._cards:
            self._card_layout.removeWidget(card)
        for card in removed_cards:
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for card in next_cards:
            self.add_card(card)

    def cards(self) -> tuple[QWidget, ...]:
        """Return the cards owned by this group in visual order."""

        return tuple(self._cards)

    def _build_layout(self) -> None:
        """Create the group header and card stack layout."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SETTINGS_CARD_GROUP_TITLE_BOTTOM_MARGIN)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        self._card_container = QWidget(self)
        self._card_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._card_container.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(SETTINGS_CARD_GROUP_SPACING)
        layout.addWidget(self._card_container)


__all__ = [
    "SETTINGS_CARD_GROUP_SPACING",
    "SettingsCardGroup",
]
