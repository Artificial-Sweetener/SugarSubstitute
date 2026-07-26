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

"""Own source-line chrome configuration and geometry preparation."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor
from qfluentwidgets import isDarkTheme, themeColor  # type: ignore[import-untyped]

from ..geometry.aggregate import PromptProjectionGeometry
from ..geometry.models import PromptProjectionSourceLineRect
from .source_line_render_state import (
    EMPTY_SOURCE_LINE_CHROME_LAYER,
    PromptSourceLineChromeLayer,
    PromptSourceLineChromeLayerKey,
    PromptSourceLineFill,
)


class PromptSourceLineChrome:
    """Own source-line configuration and its prepared render layer."""

    def __init__(self) -> None:
        """Initialize disabled source-line chrome with no reserved inset."""

        self._enabled = False
        self._content_left_inset = 0.0
        self._layer = EMPTY_SOURCE_LINE_CHROME_LAYER

    @property
    def enabled(self) -> bool:
        """Return whether source-line backgrounds should be painted."""

        return self._enabled

    @property
    def content_left_inset(self) -> float:
        """Return viewport-local space reserved for source-line chrome."""

        return self._content_left_inset

    @property
    def layer(self) -> PromptSourceLineChromeLayer:
        """Return the currently published immutable source-line layer."""

        return self._layer

    def set_enabled(self, enabled: bool) -> bool:
        """Store source-line chrome visibility and report whether it changed."""

        if self._enabled == enabled:
            return False
        self._enabled = enabled
        return True

    def set_content_left_inset(self, inset: float) -> bool:
        """Store reserved source-line inset and report whether it changed."""

        inset = max(0.0, inset)
        if abs(self._content_left_inset - inset) < 0.01:
            return False
        self._content_left_inset = inset
        return True

    def source_line_rects(
        self,
        *,
        geometry: PromptProjectionGeometry,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[PromptProjectionSourceLineRect, ...]:
        """Return visible source logical line rects aligned to projection."""

        return geometry.source_lines.visible_rects(
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def current_source_line_index(
        self,
        *,
        geometry: PromptProjectionGeometry,
        cursor_position: int,
    ) -> int:
        """Return the newline-delimited source line containing the cursor."""

        return geometry.caret.source_line_index_for_position(cursor_position)

    def prepare(
        self,
        *,
        geometry: PromptProjectionGeometry,
        geometry_identity: int,
        viewport_rect: QRectF,
        scroll_offset: float,
        cursor_position: int,
        focus_active: bool,
    ) -> bool:
        """Publish source-line commands when their complete identity changes."""

        if not self._enabled:
            return self._clear_layer()
        current_line_index = self.current_source_line_index(
            geometry=geometry,
            cursor_position=cursor_position,
        )
        dark_theme = bool(isDarkTheme())
        theme_color = QColor(themeColor())
        key = PromptSourceLineChromeLayerKey(
            geometry_identity=geometry_identity,
            viewport=_rect_key(viewport_rect),
            scroll_offset=_coordinate(scroll_offset),
            current_line_index=current_line_index,
            focus_active=focus_active,
            dark_theme=dark_theme,
            theme_color_rgba=int(theme_color.rgba()),
        )
        if self._layer.key == key:
            return False
        zebra = QColor(255, 255, 255, 16) if dark_theme else QColor(0, 0, 0, 12)
        theme_color.setAlpha(38 if dark_theme else 34)
        fills: list[PromptSourceLineFill] = []
        for source_line in self.source_line_rects(
            geometry=geometry,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        ):
            if source_line.line_index % 2 == 1:
                fills.append(_fill_command(source_line.rect, zebra))
            if source_line.line_index == current_line_index and focus_active:
                fills.append(_fill_command(source_line.rect, theme_color))
        self._layer = PromptSourceLineChromeLayer(key=key, fills=tuple(fills))
        return True

    def _clear_layer(self) -> bool:
        """Discard prepared commands while source-line chrome is disabled."""

        if self._layer.key is None and not self._layer.fills:
            return False
        self._layer = EMPTY_SOURCE_LINE_CHROME_LAYER
        return True


def _fill_command(rect: QRectF, color: QColor) -> PromptSourceLineFill:
    """Copy mutable Qt values into one immutable fill command."""

    return PromptSourceLineFill(
        left=rect.left(),
        top=rect.top(),
        width=rect.width(),
        height=rect.height(),
        color_rgba=int(color.rgba()),
    )


def _rect_key(rect: QRectF) -> tuple[int, int, int, int]:
    """Quantize one viewport rectangle for stable layer identity."""

    return (
        _coordinate(rect.x()),
        _coordinate(rect.y()),
        _coordinate(rect.width()),
        _coordinate(rect.height()),
    )


def _coordinate(value: float) -> int:
    """Quantize one geometry coordinate without losing subpixel identity."""

    return int(round(value * 100.0))


__all__ = [
    "PromptSourceLineChrome",
]
