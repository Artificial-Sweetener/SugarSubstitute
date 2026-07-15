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

"""Own prompt projection text metrics and row geometry calculations."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSizeF
from PySide6.QtGui import QFont, QFontMetricsF


def projection_text_line_height(base_font: QFont) -> float:
    """Return the authoritative text-only projection row height for a font."""

    return max(1.0, float(QFontMetricsF(base_font).lineSpacing()))


@dataclass(frozen=True, slots=True)
class PromptProjectionMetrics:
    """Define the single geometry contract for one projection layout pass."""

    base_font: QFont
    base_font_key: str
    text_line_height: float
    text_ascent: float
    text_descent: float
    document_margin: float
    content_left_inset: float
    wrap_width: float

    @property
    def content_left(self) -> float:
        """Return the left edge used for prompt projection content."""

        return self.document_margin + max(0.0, self.content_left_inset)

    @property
    def content_width(self) -> float:
        """Return the wrapping width available to projection content."""

        return max(
            1.0,
            self.wrap_width
            - (self.document_margin * 2.0)
            - max(0.0, self.content_left_inset),
        )

    def initial_line_top(self) -> float:
        """Return the document-local top of the first projection row."""

        return self.document_margin

    def initial_row_height(self) -> float:
        """Return the row height for a text-only visual row."""

        return self.text_line_height

    def row_height_with_inline_object(self, row_height: float, size: QSizeF) -> float:
        """Return row height after an inline object participates in the row."""

        return max(row_height, float(size.height()))

    def text_top_for_row(self, *, row_top: float, row_height: float) -> float:
        """Return the document-local top of normal text inside a projection row."""

        return row_top + max(0.0, (row_height - self.text_line_height) / 2.0)

    def text_baseline_for_row(self, *, row_top: float, row_height: float) -> float:
        """Return the document-local baseline of normal text inside a row."""

        return self.text_top_for_row(row_top=row_top, row_height=row_height) + (
            self.text_ascent
        )

    def text_fragment_rect(
        self,
        *,
        x_left: float,
        row_top: float,
        row_height: float,
        width: float,
    ) -> QRectF:
        """Return the document-local rect for a normal text fragment."""

        return QRectF(
            x_left,
            self.text_top_for_row(row_top=row_top, row_height=row_height),
            max(1.0, width),
            self.text_line_height,
        )

    def text_advance(self, text: str) -> float:
        """Return the horizontal advance for normal editor text."""

        return float(QFontMetricsF(self.base_font).horizontalAdvance(text))

    def caret_rect(self, *, x_left: float, row_top: float, row_height: float) -> QRectF:
        """Return the document-local caret rect for one projection row boundary."""

        return QRectF(x_left, row_top, 1.0, row_height)

    def inline_object_rect(
        self,
        *,
        x_left: float,
        row_top: float,
        row_height: float,
        size: QSizeF,
    ) -> QRectF:
        """Return the document-local rect for one inline object inside a row."""

        object_top = row_top + max(0.0, (row_height - size.height()) / 2.0)
        return QRectF(x_left, object_top, size.width(), size.height())

    def content_height_for_rows(self, row_heights: tuple[float, ...]) -> float:
        """Return document content height for finalized projection row heights."""

        return self.document_margin + sum(row_heights) + self.document_margin


class PromptProjectionMetricsFactory:
    """Build immutable metrics snapshots for prompt projection layout passes."""

    def create(
        self,
        *,
        base_font: QFont,
        document_margin: float,
        wrap_width: float,
        content_left_inset: float = 0.0,
    ) -> PromptProjectionMetrics:
        """Return projection metrics derived from the current editor geometry."""

        base_font_copy = QFont(base_font)
        base_metrics = QFontMetricsF(base_font_copy)
        text_line_height = projection_text_line_height(base_font_copy)
        return PromptProjectionMetrics(
            base_font=base_font_copy,
            base_font_key=base_font_copy.toString(),
            text_line_height=text_line_height,
            text_ascent=float(base_metrics.ascent()),
            text_descent=float(base_metrics.descent()),
            document_margin=float(document_margin),
            content_left_inset=float(content_left_inset),
            wrap_width=float(wrap_width),
        )
