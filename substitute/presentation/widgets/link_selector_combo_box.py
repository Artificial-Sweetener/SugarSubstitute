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

"""Provide closed-label compaction rules for prompt/node link selector combos."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QWidget

from .combo_box import _COMBO_TEXT_CHROME_WIDTH, ComboBox

_LINK_PREFIX = "🔗 "


@dataclass(frozen=True, slots=True)
class _ParsedLinkLabel:
    """Represent the route-qualified portions of one linked cube label."""

    full_label: str
    compact_label: str


def _parsed_link_label(text: str) -> _ParsedLinkLabel | None:
    """Return compact display candidates for one route-qualified linked label."""

    if not text.startswith(_LINK_PREFIX):
        return None
    routed_text = text[len(_LINK_PREFIX) :]
    route_index = routed_text.rfind("/")
    if route_index <= 0:
        return None
    tail_text = routed_text[route_index + 1 :].strip()
    if not tail_text:
        return None
    return _ParsedLinkLabel(
        full_label=text,
        compact_label=f"{_LINK_PREFIX}{tail_text}",
    )


class LinkSelectorComboBox(ComboBox):
    """Display prompt/node link labels by surrendering route prefixes first."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize link-label compaction with no shared width preference."""

        super().__init__(parent)
        self._shared_preferred_width: int | None = None

    def setSharedPreferredWidth(self, width: int | None) -> None:
        """Set the shared preferred width without constraining shrink behavior."""

        self._shared_preferred_width = None if width is None else max(0, width)
        self.updateGeometry()

    def sharedPreferredWidth(self) -> int | None:
        """Return the configured shared preferred width, when one exists."""

        return self._shared_preferred_width

    def sizeHint(self) -> QSize:
        """Return the item-based hint expanded to the shared preferred width."""

        hint = super().sizeHint()
        shared_width = self.sharedPreferredWidth()
        if shared_width is None:
            return hint
        return QSize(max(hint.width(), shared_width), hint.height())

    def _closed_display_text_for_width(self, width: int) -> str:
        """Return closed text that favors the final route segment under pressure."""

        display_text = self._closed_display_text()
        available_width = max(0, width - self._closed_display_text_chrome_width())
        if not display_text or available_width <= 0:
            return self.fontMetrics().elidedText(
                display_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )

        parsed = _parsed_link_label(display_text)
        if parsed is None:
            return self.fontMetrics().elidedText(
                display_text,
                Qt.TextElideMode.ElideRight,
                available_width,
            )

        if self.fontMetrics().horizontalAdvance(parsed.full_label) <= available_width:
            return parsed.full_label
        if (
            self.fontMetrics().horizontalAdvance(parsed.compact_label)
            <= available_width
        ):
            return parsed.compact_label
        return self.fontMetrics().elidedText(
            parsed.compact_label,
            Qt.TextElideMode.ElideRight,
            available_width,
        )


__all__ = ["LinkSelectorComboBox", "_COMBO_TEXT_CHROME_WIDTH"]
