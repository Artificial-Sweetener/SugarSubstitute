#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Map Python text coordinates to Qt UTF-16 and Unicode grapheme boundaries."""

from __future__ import annotations

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

        target = min(max(0, utf16_offset), self.utf16_length)
        if target == 0:
            return 0
        consumed = 0
        for index, character in enumerate(self.text):
            next_consumed = consumed + _utf16_code_units(character)
            if target < next_consumed:
                return index + 1 if prefer_after else index
            if target == next_consumed:
                return index + 1
            consumed = next_consumed
        return len(self.text)

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
        return tuple(
            self.utf16_to_python(boundary, prefer_after=True)
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

    return len(character.encode("utf-16-le", errors="surrogatepass")) // 2


__all__ = ["TextCoordinateMap"]
