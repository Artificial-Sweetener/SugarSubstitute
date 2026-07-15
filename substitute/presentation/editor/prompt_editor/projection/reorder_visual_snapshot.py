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
]
