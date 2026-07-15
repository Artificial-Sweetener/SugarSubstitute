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

"""Provide static attached-row Settings cards without accordion behavior."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from substitute.presentation.settings.settings_card import SettingsCard
from substitute.presentation.settings.settings_style import (
    SETTINGS_CARD_RADIUS,
    settings_card_border_color,
    settings_card_fill_color,
)


class SettingsSegmentedCard(QWidget):
    """Render one always-visible Fluent settings card with attached rows."""

    def __init__(
        self,
        *,
        rows: Iterable[QWidget] = (),
        parent: QWidget | None = None,
    ) -> None:
        """Create the segmented card and append any initial rows."""

        super().__init__(parent)
        self.setObjectName("SubstituteSettingsSegmentedCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background-color: transparent; border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._rows: list[QWidget] = []
        self._build_layout()
        for row in rows:
            self.add_row(row)

    def add_row(self, row: QWidget) -> None:
        """Append one attached row to the segmented card."""

        if self._rows:
            self._layout.addWidget(_SettingsSegmentedCardSeparator(self))
        self._rows.append(row)
        row.setParent(self)
        self._layout.addWidget(row)

    def rows(self) -> tuple[QWidget, ...]:
        """Return the visible row widgets owned by this card."""

        return tuple(self._rows)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the shared Fluent card fill and border behind all rows."""

        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(settings_card_border_color())
        painter.setBrush(settings_card_fill_color(self))
        painter.drawRoundedRect(rect, SETTINGS_CARD_RADIUS, SETTINGS_CARD_RADIUS)

    def _build_layout(self) -> None:
        """Create the vertical attached-row layout."""

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)


class SettingsSegmentedCardRow(SettingsCard):
    """Render one row inside an always-visible segmented settings card."""

    def __init__(
        self,
        *,
        title: str,
        description: str = "",
        visual_widget: QWidget | None = None,
        trailing_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create one static segmented settings row."""

        super().__init__(
            title=title,
            description=description,
            visual_widget=visual_widget,
            trailing_widget=trailing_widget,
            reserve_visual_space=True,
            appearance="segmented_item",
            wrap_no_icon_threshold=0,
            parent=parent,
        )


class _SettingsSegmentedCardSeparator(QWidget):
    """Render one full-width separator between static segmented card rows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create a fixed-height separator."""

        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the separator line."""

        _ = event
        painter = QPainter(self)
        painter.fillRect(self.rect(), settings_card_border_color())


__all__ = ["SettingsSegmentedCard", "SettingsSegmentedCardRow"]
