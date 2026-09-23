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

"""Plan full-width text lines with one Qt shaping transaction."""

from __future__ import annotations

from PySide6.QtGui import QFont, QTextLayout, QTextOption

from substitute.presentation.text_coordinates import TextCoordinateMap

from .text_measurement import (
    PROMPT_LAYOUT_WIDTH_EPSILON,
    PromptTextMeasurementCache,
)


def plan_full_width_text_lines(
    text: str,
    *,
    font: QFont,
    content_width: float,
    wrap_option: QTextOption,
    measurement_cache: PromptTextMeasurementCache,
) -> tuple[int, ...] | None:
    """Return Python lengths for exact Qt lines, or reject ambiguous trailing space."""

    if not text:
        return ()
    coordinates = TextCoordinateMap(text)
    text_layout = QTextLayout(text, font)
    text_layout.setTextOption(wrap_option)
    text_layout.beginLayout()
    qt_lines = []
    while True:
        text_line = text_layout.createLine()
        if not text_line.isValid():
            break
        text_line.setLineWidth(max(1.0, content_width))
        qt_lines.append(text_line)
    text_layout.endLayout()

    planned_lengths: list[int] = []
    python_start = 0
    for text_line in qt_lines:
        python_end = coordinates.utf16_to_python(
            text_line.textStart() + text_line.textLength(),
            prefer_after=False,
        )
        if python_end <= python_start:
            return None
        line_text = text[python_start:python_end]
        boundary_x = measurement_cache.unwrapped_text_offsets(line_text, font)[-1]
        if boundary_x > content_width + PROMPT_LAYOUT_WIDTH_EPSILON:
            return None
        planned_lengths.append(python_end - python_start)
        python_start = python_end
    if python_start != len(text):
        return None
    return tuple(planned_lengths)


__all__ = ["plan_full_width_text_lines"]
