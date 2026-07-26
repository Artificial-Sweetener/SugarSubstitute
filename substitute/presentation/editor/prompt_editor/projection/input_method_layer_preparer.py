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

"""Shape bounded input-method preedit content before prompt painting."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QFont,
    QPalette,
    QTextCharFormat,
    QTextLayout,
    QTextLine,
)

from substitute.presentation.editor.prompt_editor.core.editing.ime import (
    PromptImePreedit,
)
from substitute.presentation.text_coordinates import TextCoordinateMap

from .input_method_render_state import (
    EMPTY_INPUT_METHOD_RENDER_LAYER,
    PromptInputMethodLayerKey,
    PromptInputMethodRenderLayer,
    PromptPreeditFormat,
)


class PromptInputMethodRenderLayerPreparer:
    """Shape one bounded preedit string into an immutable render publication."""

    def prepare(
        self,
        state: PromptImePreedit | None,
        *,
        formats: tuple[PromptPreeditFormat, ...],
        cursor_color: QColor | None,
        font: QFont,
        palette: QPalette,
        base_caret_rect: QRectF,
        previous: PromptInputMethodRenderLayer,
    ) -> PromptInputMethodRenderLayer:
        """Return a reused or newly shaped preedit render layer."""

        if state is None:
            return EMPTY_INPUT_METHOD_RENDER_LAYER
        resolved_cursor_color = (
            QColor(cursor_color)
            if cursor_color is not None
            else QColor(palette.color(QPalette.ColorRole.Text))
        )
        key = PromptInputMethodLayerKey(
            preedit=state,
            formats=formats,
            origin=_point_key(base_caret_rect.topLeft()),
            font_key=font.toString(),
            palette_key=int(palette.cacheKey()),
            cursor_rgba=int(resolved_cursor_color.rgba()),
        )
        if previous.key == key:
            return previous
        layout = _build_layout(
            state,
            formats=formats,
            font=font,
            palette=palette,
        )
        line = layout.lineAt(0)
        if not line.isValid():
            return PromptInputMethodRenderLayer(
                key=key,
                layout=None,
                origin=(base_caret_rect.x(), base_caret_rect.y()),
                cursor_line=None,
                cursor_rgba=int(resolved_cursor_color.rgba()),
                candidate_rect=_rect_values(base_caret_rect),
            )
        cursor_x = _cursor_x(line, state.cursor_utf16)
        origin = base_caret_rect.topLeft()
        cursor_line = (
            origin.x() + cursor_x,
            origin.y(),
            origin.x() + cursor_x,
            origin.y() + line.height(),
        )
        candidate_rect = QRectF(
            origin.x() + cursor_x,
            origin.y(),
            max(1.0, base_caret_rect.width()),
            max(base_caret_rect.height(), line.height()),
        )
        return PromptInputMethodRenderLayer(
            key=key,
            layout=layout,
            origin=(origin.x(), origin.y()),
            cursor_line=cursor_line if state.cursor_visible else None,
            cursor_rgba=int(resolved_cursor_color.rgba()),
            candidate_rect=_rect_values(candidate_rect),
        )


def _build_layout(
    state: PromptImePreedit,
    *,
    formats: tuple[PromptPreeditFormat, ...],
    font: QFont,
    palette: QPalette,
) -> QTextLayout:
    """Shape one preedit string and preserve its supplied format ranges."""

    layout = QTextLayout(state.text, font)
    layout_formats = [
        _layout_format_range(
            start=format_range.start,
            length=format_range.length,
            text_format=format_range.text_format,
        )
        for format_range in formats
    ]
    if not layout_formats:
        default_format = QTextCharFormat()
        default_format.setForeground(palette.brush(QPalette.ColorRole.Text))
        default_format.setFontUnderline(True)
        layout_formats.append(
            _layout_format_range(
                start=0,
                length=TextCoordinateMap(state.text).utf16_length,
                text_format=default_format,
            )
        )
    layout.setFormats(layout_formats)
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(1_000_000.0)
    layout.endLayout()
    return layout


def _cursor_x(line: QTextLine, utf16_position: int) -> float:
    """Return a shaped line x-coordinate for a clamped UTF-16 position."""

    cursor_to_x = cast(tuple[float, int], line.cursorToX(max(0, utf16_position)))
    return float(cursor_to_x[0])


def _layout_format_range(
    *,
    start: int,
    length: int,
    text_format: QTextCharFormat,
) -> QTextLayout.FormatRange:
    """Build one mutable Qt layout format range with typed assignments."""

    format_range = QTextLayout.FormatRange()
    format_range.start = start
    format_range.length = length
    format_range.format = text_format
    return format_range


def _point_key(point: QPointF) -> tuple[int, int]:
    """Quantize one viewport point for exact render-layer reuse."""

    return _coordinate(point.x()), _coordinate(point.y())


def _rect_values(rect: QRectF) -> tuple[float, float, float, float]:
    """Copy one mutable Qt rectangle into scalar geometry."""

    return rect.x(), rect.y(), rect.width(), rect.height()


def _coordinate(value: float) -> int:
    """Quantize one viewport coordinate without losing subpixel identity."""

    return int(round(value * 100.0))


__all__ = ["PromptInputMethodRenderLayerPreparer"]
