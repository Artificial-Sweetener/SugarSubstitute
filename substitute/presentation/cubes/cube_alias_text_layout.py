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

"""Lay out cube alias text shared by cube-card painting and editing."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter

from substitute.application.cubes.cube_alias_display import (
    CubeAliasDisplayParts as CubeAliasTextParts,
    split_cube_alias_prefix,
)

_PREFIX_FONT_SCALE = 0.6
_MAX_PREFIX_WIDTH_FRACTION = 0.45
# Qt may elide text whose advance exactly matches its available width.
_PREFIX_ELISION_ALLOWANCE = 2.0


@dataclass(frozen=True)
class CubeAliasTextSegment:
    """Describe one laid-out cube alias text segment."""

    text: str
    start: int
    end: int
    rect: QRectF
    font: QFont
    baseline_y: float
    token: bool


@dataclass(frozen=True)
class CubeAliasTextLayout:
    """Describe full primary-row layout for one cube alias."""

    full_text: str
    parts: CubeAliasTextParts
    row_rect: QRectF
    baseline_y: float
    prefix_segment: CubeAliasTextSegment | None
    body_segment: CubeAliasTextSegment


def cube_alias_prefix_font(primary_font: QFont) -> QFont:
    """Return the reduced font used for a leading cube alias prefix."""

    prefix_font = QFont(primary_font)
    point_size = prefix_font.pointSizeF()
    if point_size > 0:
        prefix_font.setPointSizeF(max(1.0, point_size * _PREFIX_FONT_SCALE))
        return prefix_font
    pixel_size = prefix_font.pixelSize()
    if pixel_size > 0:
        prefix_font.setPixelSize(max(1, round(pixel_size * _PREFIX_FONT_SCALE)))
    return prefix_font


def cube_alias_primary_baseline_y(
    painter: QPainter,
    *,
    row_rect: QRectF,
    primary_font: QFont,
) -> float:
    """Return the primary body baseline used by prefix and body text."""

    painter.save()
    painter.setFont(primary_font)
    metrics = painter.fontMetrics()
    baseline_y = row_rect.y() + ((row_rect.height() - metrics.height()) / 2)
    baseline_y += metrics.ascent()
    painter.restore()
    return baseline_y


def layout_cube_alias_text(
    painter: QPainter,
    *,
    text: str,
    row_rect: QRectF,
    primary_font: QFont,
) -> CubeAliasTextLayout:
    """Return render and hit-test geometry for one cube alias line."""

    parts = split_cube_alias_prefix(text)
    baseline_y = cube_alias_primary_baseline_y(
        painter,
        row_rect=row_rect,
        primary_font=primary_font,
    )
    if not parts.prefix:
        return CubeAliasTextLayout(
            full_text=text,
            parts=parts,
            row_rect=QRectF(row_rect),
            baseline_y=baseline_y,
            prefix_segment=None,
            body_segment=CubeAliasTextSegment(
                text=parts.body,
                start=0,
                end=len(parts.body),
                rect=QRectF(row_rect),
                font=QFont(primary_font),
                baseline_y=baseline_y,
                token=False,
            ),
        )

    prefix_font = cube_alias_prefix_font(primary_font)
    prefix_width = _bounded_prefix_width(
        painter,
        text=parts.prefix,
        font=prefix_font,
        available_width=row_rect.width(),
    )
    prefix_rect = QRectF(row_rect.x(), row_rect.y(), prefix_width, row_rect.height())
    body_rect = QRectF(
        row_rect.x() + prefix_width,
        row_rect.y(),
        max(0.0, row_rect.width() - prefix_width),
        row_rect.height(),
    )
    prefix_end = len(parts.prefix)
    return CubeAliasTextLayout(
        full_text=text,
        parts=parts,
        row_rect=QRectF(row_rect),
        baseline_y=baseline_y,
        prefix_segment=CubeAliasTextSegment(
            text=parts.prefix,
            start=0,
            end=prefix_end,
            rect=prefix_rect,
            font=prefix_font,
            baseline_y=baseline_y,
            token=True,
        ),
        body_segment=CubeAliasTextSegment(
            text=parts.body,
            start=prefix_end,
            end=len(text),
            rect=body_rect,
            font=QFont(primary_font),
            baseline_y=baseline_y,
            token=False,
        ),
    )


def prefix_token_range(text: str) -> tuple[int, int] | None:
    """Return the atomic prefix-token range for one alias when present."""

    parts = split_cube_alias_prefix(text)
    if not parts.prefix:
        return None
    return (0, len(parts.prefix))


def _bounded_prefix_width(
    painter: QPainter,
    *,
    text: str,
    font: QFont,
    available_width: float,
) -> float:
    """Return bounded prefix width that prevents avoidable prefix elision."""

    if available_width <= 0:
        return 0.0
    painter.save()
    painter.setFont(font)
    natural_width = painter.fontMetrics().horizontalAdvance(text)
    painter.restore()
    max_prefix_width = max(0.0, available_width * _MAX_PREFIX_WIDTH_FRACTION)
    required_width = float(natural_width) + _PREFIX_ELISION_ALLOWANCE
    return min(required_width, max_prefix_width)


__all__ = [
    "CubeAliasTextLayout",
    "CubeAliasTextParts",
    "CubeAliasTextSegment",
    "cube_alias_prefix_font",
    "cube_alias_primary_baseline_y",
    "layout_cube_alias_text",
    "prefix_token_range",
    "split_cube_alias_prefix",
]
