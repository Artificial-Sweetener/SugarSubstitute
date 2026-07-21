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

"""Snapshot projection paint data for animated reorder chip displacement."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPalette

from .model import PromptProjectionRun, PromptProjectionToken
from .tokens import PromptRichInlineObjectRenderer


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshotKey:
    """Identify one projection paint snapshot against editor visual state."""

    source_revision: int
    viewport_rect: QRect
    scroll_offset: int
    font_key: str
    palette_key: int
    preview_generation: int | None
    geometry_generation: int
    segment_index: int
    mode: str


@dataclass(frozen=True, slots=True)
class PromptReorderTextPaintFragment:
    """Carry already-laid-out text paint data for one reorder chip fragment."""

    text: str
    font: QFont
    baseline: QPointF
    text_rect: QRectF
    color: QColor


@dataclass(frozen=True, slots=True)
class PromptReorderInlineObjectPaintFragment:
    """Carry already-laid-out inline object paint data for one reorder chip fragment."""

    renderer: PromptRichInlineObjectRenderer
    rect: QRectF
    run: PromptProjectionRun
    token: PromptProjectionToken
    base_font: QFont
    palette: QPalette


PromptReorderProjectionPaintFragment = (
    PromptReorderTextPaintFragment | PromptReorderInlineObjectPaintFragment
)


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionPaintSnapshot:
    """Carry projection-owned paint fragments represented by one overlay chip."""

    key: PromptReorderProjectionSnapshotKey
    fragments: tuple[PromptReorderProjectionPaintFragment, ...]
    source_ranges: tuple[tuple[int, int], ...]
    content_key: object

    @property
    def viewport_rects(self) -> tuple[QRectF, ...]:
        """Return the exact viewport-local rectangles represented by this snapshot."""

        return tuple(
            fragment.text_rect
            if isinstance(fragment, PromptReorderTextPaintFragment)
            else fragment.rect
            for fragment in self.fragments
        )

    @property
    def text_fragments(self) -> tuple[PromptReorderTextPaintFragment, ...]:
        """Return text fragments contained in this paint snapshot."""

        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, PromptReorderTextPaintFragment)
        )

    @property
    def inline_object_fragments(
        self,
    ) -> tuple[PromptReorderInlineObjectPaintFragment, ...]:
        """Return inline object fragments contained in this paint snapshot."""

        return tuple(
            fragment
            for fragment in self.fragments
            if isinstance(fragment, PromptReorderInlineObjectPaintFragment)
        )


def reorder_projection_paint_content_key(
    fragments: tuple[PromptReorderProjectionPaintFragment, ...],
) -> object:
    """Return a placement-independent identity for immutable paint fragments."""

    origin = _paint_fragment_origin(fragments)
    return tuple(
        _paint_fragment_content_key(fragment, origin=origin) for fragment in fragments
    )


def _paint_fragment_origin(
    fragments: tuple[PromptReorderProjectionPaintFragment, ...],
) -> QPointF:
    """Return the top-left origin shared by one chip's paint fragments."""

    if not fragments:
        return QPointF()
    rects = tuple(
        fragment.text_rect
        if isinstance(fragment, PromptReorderTextPaintFragment)
        else fragment.rect
        for fragment in fragments
    )
    return QPointF(
        min(rect.left() for rect in rects),
        min(rect.top() for rect in rects),
    )


def _paint_fragment_content_key(
    fragment: PromptReorderProjectionPaintFragment,
    *,
    origin: QPointF,
) -> object:
    """Return one fragment identity normalized to chip-local coordinates."""

    if isinstance(fragment, PromptReorderTextPaintFragment):
        return (
            "text",
            fragment.text,
            fragment.font.toString(),
            fragment.color.rgba(),
            _relative_point_key(fragment.baseline, origin=origin),
            _relative_rect_key(fragment.text_rect, origin=origin),
        )
    return (
        "inline",
        _relative_rect_key(fragment.rect, origin=origin),
        repr(fragment.run),
        repr(fragment.token),
        fragment.base_font.toString(),
        int(fragment.palette.cacheKey()),
    )


def _relative_rect_key(
    rect: QRectF,
    *,
    origin: QPointF,
) -> tuple[float, float, float, float]:
    """Return a rounded rect in chip-local coordinates."""

    return (
        _rounded(rect.left() - origin.x()),
        _rounded(rect.top() - origin.y()),
        _rounded(rect.width()),
        _rounded(rect.height()),
    )


def _relative_point_key(
    point: QPointF,
    *,
    origin: QPointF,
) -> tuple[float, float]:
    """Return a rounded point in chip-local coordinates."""

    return (_rounded(point.x() - origin.x()), _rounded(point.y() - origin.y()))


def _rounded(value: float) -> float:
    """Return stable precision for projection paint identity."""

    return round(float(value), 3)


def paint_reorder_projection_snapshot(
    painter: QPainter,
    snapshot: PromptReorderProjectionPaintSnapshot,
) -> None:
    """Paint one cached projection snapshot without measuring or relayout."""

    for fragment in snapshot.fragments:
        if isinstance(fragment, PromptReorderTextPaintFragment):
            painter.setFont(fragment.font)
            painter.setPen(fragment.color)
            painter.drawText(fragment.baseline, fragment.text)
            continue
        fragment.renderer.paint_inline_object(
            painter,
            fragment.rect,
            fragment.run,
            fragment.token,
            base_font=fragment.base_font,
            palette=fragment.palette,
            selected=False,
        )


__all__ = [
    "PromptReorderInlineObjectPaintFragment",
    "PromptReorderProjectionPaintFragment",
    "PromptReorderProjectionPaintSnapshot",
    "PromptReorderProjectionSnapshotKey",
    "PromptReorderTextPaintFragment",
    "paint_reorder_projection_snapshot",
    "reorder_projection_paint_content_key",
]
