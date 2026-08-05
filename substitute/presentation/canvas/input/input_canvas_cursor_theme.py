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

"""Resolve SugarSubstitute cursor artwork for semantic CuteCanvas feedback."""

from __future__ import annotations

import math
from pathlib import Path

from cutecanvas import EditorCursorIntent
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QCursor, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_CURSOR_SIZE = 40
_CURSOR_HOTSPOT = (6, 3)
_CURSOR_DIRECTORY = Path(__file__).resolve().parents[2] / "resources" / "cursors"
_CURSOR_RESOURCES = {
    EditorCursorIntent.SELECTION_TRANSLATE: _CURSOR_DIRECTORY
    / "SelectionTranslateCursor.svg",
    EditorCursorIntent.MOVE: _CURSOR_DIRECTORY / "SelectionTranslateCursor.svg",
    EditorCursorIntent.MOVE_CUT: _CURSOR_DIRECTORY / "MoveCutCursor.svg",
}


class InputCanvasCursorTheme:
    """Cache application-owned artwork for CuteCanvas semantic cursor intents."""

    def __init__(self) -> None:
        """Initialize an empty DPR-keyed cursor cache."""

        self._cursors: dict[tuple[EditorCursorIntent, float], QCursor] = {}

    def resolve_cursor(
        self,
        intent: EditorCursorIntent,
        *,
        device_pixel_ratio: float,
    ) -> QCursor | None:
        """Resolve supported Sugar artwork and defer other intents to CuteCanvas."""

        resource = _CURSOR_RESOURCES.get(intent)
        if resource is None:
            return None
        requested_dpr = float(device_pixel_ratio)
        dpr = (
            1.0
            if not math.isfinite(requested_dpr) or requested_dpr <= 0.0
            else round(max(0.025, requested_dpr), 6)
        )
        key = intent, dpr
        cached = self._cursors.get(key)
        if cached is not None:
            return cached
        cursor = self._render_cursor(resource, dpr)
        self._cursors[key] = cursor
        return cursor

    @staticmethod
    def _render_cursor(resource: Path, device_pixel_ratio: float) -> QCursor:
        """Render one high-contrast Fluent-derived cursor with an explicit hotspot."""

        renderer = QSvgRenderer(str(resource))
        if not renderer.isValid():
            raise RuntimeError(f"Invalid Input canvas cursor resource: {resource}")
        image = QImage(
            QSize(
                round(_CURSOR_SIZE * device_pixel_ratio),
                round(_CURSOR_SIZE * device_pixel_ratio),
            ),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(device_pixel_ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(
            painter,
            QRectF(0.0, 0.0, float(_CURSOR_SIZE), float(_CURSOR_SIZE)),
        )
        painter.end()
        return QCursor(
            QPixmap.fromImage(image),
            _CURSOR_HOTSPOT[0],
            _CURSOR_HOTSPOT[1],
        )


__all__ = ["InputCanvasCursorTheme"]
