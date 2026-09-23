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

"""Identify source text whose grapheme boundaries need no Unicode segmentation."""

from __future__ import annotations


def simple_code_point_boundaries(text: str) -> range | None:
    """Return direct boundaries only when every code point is independently safe."""

    if text.isascii() and "\r\n" not in text:
        return range(len(text) + 1)
    return None


__all__ = ["simple_code_point_boundaries"]
