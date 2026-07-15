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

"""Paint projection-owned reorder chip geometry and projection-backed text."""

from __future__ import annotations

from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from .layout_engine import PromptProjectionLayout
from .model import PromptProjectionSelection
from .reorder_chip_geometry import PromptReorderChipGeometry


class PromptProjectionChipPaintStyle(Protocol):
    """Describe the chip paint style shape consumed by projection painting."""

    @property
    def fill_color(self) -> QColor:
        """Return the fill color for solid chrome."""
        ...

    @property
    def border_color(self) -> QColor:
        """Return the border color for chip chrome."""
        ...

    @property
    def outline_only(self) -> bool:
        """Return whether the chip should be painted as outline-only."""
        ...

    @property
    def outline_width(self) -> float:
        """Return the outline stroke width."""
        ...

    @property
    def opacity(self) -> float:
        """Return the painter opacity for this chip."""
        ...


class PromptProjectionChipTextVisual(Protocol):
    """Describe the visual text translation needed by projection text painting."""

    @property
    def text_translation(self) -> QPointF | None:
        """Return the translation applied before painting projection text."""
        ...


class PromptProjectionChipTextPaintPayload(Protocol):
    """Describe prepared projection text state consumed by chrome-only overlays."""

    @property
    def layout(self) -> PromptProjectionLayout:
        """Return the prepared projection layout used for text painting."""
        ...

    @property
    def source_text(self) -> str:
        """Return the source text represented by the prepared projection payload."""
        ...


class PromptProjectionChipPainter:
    """Paint projection-owned semantic chip geometry and projected chip text."""

    def paint_chip_geometry(
        self,
        *,
        painter: QPainter,
        geometry: PromptReorderChipGeometry,
        style: PromptProjectionChipPaintStyle,
    ) -> None:
        """Paint one semantic projection-owned reorder chip geometry."""

        painter.save()
        painter.setOpacity(style.opacity)
        painter.setBrush(
            Qt.BrushStyle.NoBrush if style.outline_only else QColor(style.fill_color)
        )
        painter.setPen(QPen(style.border_color, style.outline_width))
        painter.drawPath(geometry.chrome_path)
        painter.restore()

    def paint_projection_text(
        self,
        *,
        painter: QPainter,
        layout: PromptProjectionLayout,
        visual: PromptProjectionChipTextVisual,
        clip_rect: QRectF,
        selection: PromptProjectionSelection | None = None,
        scroll_offset: float = 0.0,
    ) -> None:
        """Paint one projection-backed chip label through the shared layout path."""

        text_translation = visual.text_translation
        if text_translation is None:
            return
        painter.save()
        painter.translate(QPointF(text_translation))
        layout.draw(
            painter,
            selection=selection,
            scroll_offset=scroll_offset,
            clip_rect=clip_rect,
        )
        painter.restore()

    def paint_projection_text_payload(
        self,
        *,
        painter: QPainter,
        payload: PromptProjectionChipTextPaintPayload,
        visual: PromptProjectionChipTextVisual,
        clip_rect: QRectF,
    ) -> None:
        """Paint prepared projection text from an opaque projection payload."""

        self.paint_projection_text(
            painter=painter,
            layout=payload.layout,
            visual=visual,
            clip_rect=clip_rect,
        )


__all__ = [
    "PromptProjectionChipPainter",
    "PromptProjectionChipTextPaintPayload",
    "PromptProjectionChipPaintStyle",
    "PromptProjectionChipTextVisual",
]
