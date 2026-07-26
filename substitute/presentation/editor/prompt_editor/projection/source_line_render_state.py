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

"""Define immutable source-line commands consumed by prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSourceLineChromeLayerKey:
    """Identify one exact source-line geometry and visual state."""

    geometry_identity: int
    viewport: tuple[int, int, int, int]
    scroll_offset: int
    current_line_index: int
    focus_active: bool
    dark_theme: bool
    theme_color_rgba: int


@dataclass(frozen=True, slots=True)
class PromptSourceLineFill:
    """Describe one immutable source-line fill command."""

    left: float
    top: float
    width: float
    height: float
    color_rgba: int


@dataclass(frozen=True, slots=True)
class PromptSourceLineChromeLayer:
    """Contain all prepared source-line fill commands for one revision."""

    key: PromptSourceLineChromeLayerKey | None
    fills: tuple[PromptSourceLineFill, ...]


EMPTY_SOURCE_LINE_CHROME_LAYER = PromptSourceLineChromeLayer(key=None, fills=())


__all__ = [
    "EMPTY_SOURCE_LINE_CHROME_LAYER",
    "PromptSourceLineChromeLayer",
    "PromptSourceLineChromeLayerKey",
    "PromptSourceLineFill",
]
