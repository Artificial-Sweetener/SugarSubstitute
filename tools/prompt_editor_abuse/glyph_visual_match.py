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

"""Match expected prompt glyph footprints against captured backing-store pixels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter


class ExpectedGlyphFragment(Protocol):
    """Expose the prepared text paint fields needed for pixel matching."""

    @property
    def text(self) -> str:
        """Return the prepared glyph text."""

        ...

    @property
    def font(self) -> QFont:
        """Return the prepared glyph font."""

        ...

    @property
    def baseline(self) -> QPointF:
        """Return the prepared glyph baseline."""

        ...

    @property
    def text_rect(self) -> QRectF:
        """Return the prepared glyph bounds."""

        ...

    @property
    def color(self) -> QColor:
        """Return the prepared glyph color."""

        ...


@dataclass(frozen=True, slots=True)
class FragmentPixelMatchEvidence:
    """Describe one expected fragment's visible glyph-pixel comparison."""

    visible_bounds: QRect
    expected_pixel_count: int
    matching_pixel_count: int

    @property
    def result(self) -> bool | None:
        """Return the thresholded result, or none when no glyph pixel is visible."""

        if self.expected_pixel_count == 0:
            return None
        return self.matching_pixel_count / self.expected_pixel_count >= 0.2

    @property
    def matching_ratio(self) -> float | None:
        """Return the matching fraction when the visible mask contains glyphs."""

        if self.expected_pixel_count == 0:
            return None
        return self.matching_pixel_count / self.expected_pixel_count


def fragment_has_expected_pixels(
    image: QImage,
    *,
    fragment: ExpectedGlyphFragment,
    translation: QPointF,
    visible_image_rect: QRect,
) -> bool | None:
    """Return whether one visible expected glyph footprint reached the screen."""

    return fragment_pixel_match_evidence(
        image,
        fragment=fragment,
        translation=translation,
        visible_image_rect=visible_image_rect,
    ).result


def fragment_pixel_match_evidence(
    image: QImage,
    *,
    fragment: ExpectedGlyphFragment,
    translation: QPointF,
    visible_image_rect: QRect,
) -> FragmentPixelMatchEvidence:
    """Measure one expected glyph footprint against captured screen pixels."""

    translated_rect = fragment.text_rect.translated(translation)
    bounds = translated_rect.toAlignedRect().adjusted(-1, -1, 1, 1)
    visible_bounds = bounds.intersected(visible_image_rect).intersected(image.rect())
    if visible_bounds.isEmpty():
        return FragmentPixelMatchEvidence(
            visible_bounds=visible_bounds,
            expected_pixel_count=0,
            matching_pixel_count=0,
        )
    glyph_mask = _render_fragment_glyph_mask(
        fragment,
        bounds=bounds,
        translation=translation,
    )
    expected_red = fragment.color.red()
    expected_green = fragment.color.green()
    expected_blue = fragment.color.blue()
    expected_pixel_count = 0
    matching_pixel_count = 0
    for y in range(visible_bounds.top(), visible_bounds.bottom() + 1):
        mask_y = y - bounds.top()
        for x in range(visible_bounds.left(), visible_bounds.right() + 1):
            mask_x = x - bounds.left()
            if glyph_mask.pixelColor(mask_x, mask_y).alpha() < 72:
                continue
            expected_pixel_count += 1
            color = image.pixelColor(x, y)
            color_distance = (
                (color.red() - expected_red) ** 2
                + (color.green() - expected_green) ** 2
                + (color.blue() - expected_blue) ** 2
            )
            if color_distance <= 75**2:
                matching_pixel_count += 1
    return FragmentPixelMatchEvidence(
        visible_bounds=visible_bounds,
        expected_pixel_count=expected_pixel_count,
        matching_pixel_count=matching_pixel_count,
    )


def _render_fragment_glyph_mask(
    fragment: ExpectedGlyphFragment,
    *,
    bounds: QRect,
    translation: QPointF,
) -> QImage:
    """Render the expected glyph footprint for one prepared text fragment."""

    mask = QImage(
        max(1, bounds.width()),
        max(1, bounds.height()),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    mask.fill(0)
    painter = QPainter(mask)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(fragment.font)
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(
            fragment.baseline
            + translation
            - QPointF(float(bounds.left()), float(bounds.top())),
            fragment.text,
        )
    finally:
        painter.end()
    return mask


__all__ = [
    "ExpectedGlyphFragment",
    "FragmentPixelMatchEvidence",
    "fragment_has_expected_pixels",
    "fragment_pixel_match_evidence",
]
