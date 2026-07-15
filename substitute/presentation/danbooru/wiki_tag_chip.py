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

"""Define native chip styling used by Danbooru wiki tag chips."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor
from qfluentwidgets import isDarkTheme, themeColor  # type: ignore[import-untyped]


@dataclass(frozen=True, slots=True)
class DanbooruWikiTagChipPalette:
    """Describe the fill, border, and text colors for one tag chip."""

    fill_color: QColor
    border_color: QColor
    text_color: QColor


_CATEGORY_ACCENTS = {
    "general": QColor("#ff4f9a"),
    "artist": QColor("#f5a623"),
    "copyright": QColor("#5aa9ff"),
    "character": QColor("#52d6a1"),
    "meta": QColor("#c78cff"),
}


def tag_chip_palette_for_category(
    category_name: str | None,
    *,
    is_dark: bool | None = None,
) -> DanbooruWikiTagChipPalette:
    """Return the native palette used for one Danbooru tag chip."""

    resolved_is_dark = isDarkTheme() if is_dark is None else is_dark
    accent = QColor(_CATEGORY_ACCENTS.get(category_name or "", QColor(themeColor())))
    fill = QColor(accent)
    border = QColor(accent)
    text = QColor("#f8f8f8" if resolved_is_dark else "#141414")
    if resolved_is_dark:
        fill.setAlpha(48)
        border.setAlpha(154)
    else:
        fill.setAlpha(38)
        border.setAlpha(128)
    return DanbooruWikiTagChipPalette(
        fill_color=fill,
        border_color=border,
        text_color=text,
    )


__all__ = ["DanbooruWikiTagChipPalette", "tag_chip_palette_for_category"]
