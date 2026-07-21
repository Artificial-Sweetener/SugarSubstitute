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

"""Map Python text coordinates to Qt UTF-16 and Unicode grapheme boundaries."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from PySide6.QtCore import QTextBoundaryFinder


@dataclass(frozen=True, slots=True)
class TextCoordinateMap:
    """Provide one immutable coordinate authority for a Unicode string."""

    text: str

    @property
    def utf16_length(self) -> int:
        """Return the QString-compatible UTF-16 length of the source text."""

        return len(self.text.encode("utf-16-le", errors="surrogatepass")) // 2

    def python_to_utf16(self, python_index: int) -> int:
        """Convert a clamped Python code-point boundary to a Qt UTF-16 offset."""

        clamped_index = min(max(0, python_index), len(self.text))
        return (
            len(
                self.text[:clamped_index].encode(
                    "utf-16-le",
                    errors="surrogatepass",
                )
            )
            // 2
        )

    def utf16_to_python(self, utf16_offset: int, *, prefer_after: bool = False) -> int:
        """Convert a clamped Qt UTF-16 offset to a Python code-point boundary.

        An offset inside a surrogate pair resolves to the boundary selected by
        ``prefer_after`` so callers never split a non-BMP character.
        """

        target = max(0, utf16_offset)
        consumed = 0
        for index, character in enumerate(self.text):
            next_consumed = consumed + _utf16_code_units(character)
            if target < next_consumed:
                return index + 1 if prefer_after else index
            if target == next_consumed:
                return index + 1
            consumed = next_consumed
        return len(self.text)

    def utf16_offsets_by_python_index(self) -> tuple[int, ...]:
        """Return the Qt UTF-16 offset of every Python code-point boundary."""

        offsets = [0]
        consumed = 0
        for character in self.text:
            consumed += _utf16_code_units(character)
            offsets.append(consumed)
        return tuple(offsets)

    def grapheme_boundaries(self) -> tuple[int, ...]:
        """Return Python indices at every Unicode grapheme-cluster boundary."""

        finder = QTextBoundaryFinder(
            QTextBoundaryFinder.BoundaryType.Grapheme,
            self.text,
        )
        finder.toStart()
        utf16_boundaries = [finder.position()]
        while True:
            boundary = finder.toNextBoundary()
            if boundary < 0:
                break
            utf16_boundaries.append(boundary)
        offsets = self.utf16_offsets_by_python_index()
        return tuple(
            _python_index_for_utf16_offset(
                offsets,
                boundary,
                prefer_after=True,
            )
            for boundary in utf16_boundaries
        )

    def previous_grapheme_boundary(self, python_index: int) -> int:
        """Return the preceding grapheme boundary for a Python source index."""

        clamped_index = min(max(0, python_index), len(self.text))
        return max(
            (
                boundary
                for boundary in self.grapheme_boundaries()
                if boundary < clamped_index
            ),
            default=0,
        )

    def next_grapheme_boundary(self, python_index: int) -> int:
        """Return the following grapheme boundary for a Python source index."""

        clamped_index = min(max(0, python_index), len(self.text))
        return next(
            (
                boundary
                for boundary in self.grapheme_boundaries()
                if boundary > clamped_index
            ),
            len(self.text),
        )


def _utf16_code_units(character: str) -> int:
    """Return the UTF-16 code-unit width of one Python character."""

    return 2 if ord(character) > 0xFFFF else 1


def _python_index_for_utf16_offset(
    offsets: tuple[int, ...],
    utf16_offset: int,
    *,
    prefer_after: bool,
) -> int:
    """Resolve one clamped UTF-16 offset against Python boundary offsets."""

    if prefer_after:
        return bisect_left(offsets, utf16_offset)
    return max(0, bisect_right(offsets, utf16_offset) - 1)


__all__ = ["TextCoordinateMap"]
