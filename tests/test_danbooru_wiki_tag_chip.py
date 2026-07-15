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

"""Unit tests for Danbooru wiki tag-chip palette selection."""

from __future__ import annotations

from PySide6.QtGui import QColor

from substitute.presentation.danbooru.wiki_tag_chip import (
    tag_chip_palette_for_category,
)


def test_tag_chip_palette_uses_distinct_category_accents() -> None:
    """Different Danbooru tag categories should produce distinct chip palettes."""

    general = tag_chip_palette_for_category("general")
    character = tag_chip_palette_for_category("character")

    assert general.fill_color != character.fill_color
    assert general.border_color != character.border_color
    assert general.text_color.isValid() is True


def test_tag_chip_palette_uses_light_text_for_dark_surfaces() -> None:
    """Dark-surface chip rendering should force readable light text."""

    palette = tag_chip_palette_for_category("general", is_dark=True)

    assert palette.text_color == QColor("#f8f8f8")


def test_tag_chip_palette_uses_dark_text_for_light_surfaces() -> None:
    """Light-surface chip rendering should force readable dark text."""

    palette = tag_chip_palette_for_category("general", is_dark=False)

    assert palette.text_color == QColor("#141414")
