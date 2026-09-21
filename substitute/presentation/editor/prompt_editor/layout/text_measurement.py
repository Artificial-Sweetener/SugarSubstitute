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

"""Measure projected prompt text with bounded per-builder reuse."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from PySide6.QtGui import QFont, QFontMetricsF, QTextLayout, QTextOption

from substitute.presentation.editor.prompt_editor.core.projection.runs import (
    PromptProjectionRun,
)
from substitute.presentation.editor.prompt_editor.projection.text_style import (
    projection_text_run_font,
)
from substitute.presentation.text_coordinates import TextCoordinateMap

PROMPT_LAYOUT_WIDTH_EPSILON = 0.01


@dataclass(slots=True)
class PromptTextMeasurementCache:
    """Cache font and text measurements for canonical prompt layout builds."""

    no_wrap_option: QTextOption = field(default_factory=lambda: _text_option_no_wrap())
    wrap_option: QTextOption = field(default_factory=lambda: _text_option_word_wrap())
    offsets_by_key: dict[tuple[str, str], tuple[float, ...]] = field(
        default_factory=dict
    )
    width_by_key: dict[tuple[str, str], float] = field(default_factory=dict)
    word_fit_by_key: dict[tuple[str, str, int], bool] = field(default_factory=dict)
    font_by_run_key: dict[tuple[str, str, bool, str | None], QFont] = field(
        default_factory=dict
    )
    key_by_font_id: dict[int, tuple[QFont, str]] = field(default_factory=dict)

    def font_key(self, font: QFont) -> str:
        """Return one cached stable key for a retained Qt font wrapper."""

        font_id = id(font)
        cached = self.key_by_font_id.get(font_id)
        if cached is not None and cached[0] is font:
            return cached[1]
        key = font.toString()
        self.key_by_font_id[font_id] = (font, key)
        return key

    def font_for_run(
        self,
        run: PromptProjectionRun,
        base_font: QFont,
        *,
        base_font_key: str,
    ) -> QFont:
        """Return the projected font for one run using retained measurements."""

        key = (
            run.run_id,
            base_font_key,
            run.active,
            run.text_style_variant,
        )
        cached_font = self.font_by_run_key.get(key)
        if cached_font is not None:
            return cached_font
        font = projection_text_run_font(run, base_font)
        self.font_by_run_key[key] = font
        return font

    def unwrapped_text_offsets(self, text: str, font: QFont) -> tuple[float, ...]:
        """Return cached unwrapped cursor offsets for every text boundary."""

        if not text:
            return (0.0,)
        key = (text, self.font_key(font))
        cached_offsets = self.offsets_by_key.get(key)
        if cached_offsets is not None:
            return cached_offsets
        offsets = _unwrapped_text_offsets(
            text,
            font,
            no_wrap_option=self.no_wrap_option,
        )
        self.offsets_by_key[key] = offsets
        self.width_by_key[key] = offsets[-1]
        return offsets

    def text_width(self, text: str, font: QFont) -> float:
        """Return cached unwrapped text width."""

        key = (text, self.font_key(font))
        cached_width = self.width_by_key.get(key)
        if cached_width is not None:
            return cached_width
        return self.unwrapped_text_offsets(text, font)[-1]

    def word_fits_content_width(
        self,
        text: str,
        *,
        font: QFont,
        content_width: float,
    ) -> bool:
        """Return cached word-fit decisions for one layout width."""

        key = (text, self.font_key(font), round(content_width * 100))
        cached_fit = self.word_fit_by_key.get(key)
        if cached_fit is not None:
            return cached_fit
        fits = self.text_width(text, font) <= (
            content_width + PROMPT_LAYOUT_WIDTH_EPSILON
        )
        self.word_fit_by_key[key] = fits
        return fits

    def entry_count(self) -> int:
        """Return the approximate number of retained measurement decisions."""

        return (
            len(self.offsets_by_key)
            + len(self.width_by_key)
            + len(self.word_fit_by_key)
            + len(self.font_by_run_key)
            + len(self.key_by_font_id)
        )

    def clear(self) -> None:
        """Discard retained text measurement decisions."""

        self.offsets_by_key.clear()
        self.width_by_key.clear()
        self.word_fit_by_key.clear()
        self.font_by_run_key.clear()
        self.key_by_font_id.clear()


def _unwrapped_text_offsets(
    text: str,
    font: QFont,
    *,
    no_wrap_option: QTextOption,
) -> tuple[float, ...]:
    """Return unwrapped cursor offsets without consulting the cache."""

    if not text:
        return (0.0,)
    text_layout = QTextLayout(text, font)
    text_layout.setTextOption(no_wrap_option)
    text_layout.beginLayout()
    text_line = text_layout.createLine()
    if text_line.isValid():
        text_line.setLineWidth(
            max(1.0, QFontMetricsF(font).horizontalAdvance(text) + 1.0)
        )
    text_layout.endLayout()
    if not text_line.isValid():
        return (0.0,)
    coordinates = TextCoordinateMap(text)
    return tuple(
        float(
            cast(
                tuple[float, int],
                text_line.cursorToX(utf16_index),
            )[0]
        )
        for utf16_index in coordinates.utf16_offsets_by_python_index()
    )


def _text_option_no_wrap() -> QTextOption:
    """Return the exact unwrapped measurement configuration."""

    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.NoWrap)
    return text_option


def _text_option_word_wrap() -> QTextOption:
    """Return the canonical prompt word-wrapping configuration."""

    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    return text_option


__all__ = ["PROMPT_LAYOUT_WIDTH_EPSILON", "PromptTextMeasurementCache"]
