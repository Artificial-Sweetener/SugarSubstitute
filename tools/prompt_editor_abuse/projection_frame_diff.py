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

"""Compare live backing pixels with an isolated prepared-projection reference."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QPoint, QRectF
from PySide6.QtGui import QImage, QPainter

from substitute.presentation.editor.prompt_editor.projection.snapshot import (
    PromptProjectionTextFragment,
)

_TILE_WIDTH = 96
_MINIMUM_EXPECTED_PIXELS = 8
_MINIMUM_RETAINED_RATIO = 0.15


def missing_projection_text_tiles(
    editor: Any,
    backing_store: QImage,
) -> tuple[str, ...]:
    """Return visible layout tiles whose expected glyph pixels are absent."""

    surface = editor._surface
    layout = surface._layout
    reference = _render_projection_reference(editor)
    expected_rgba = _rgba_pixels(reference)
    actual_rgba = _rgba_pixels(backing_store)
    if expected_rgba.shape != actual_rgba.shape:
        return ("frame-size-mismatch",)
    expected_mask = expected_rgba[:, :, 3] >= 48
    color_delta = actual_rgba[:, :, :3].astype(np.int16) - expected_rgba[
        :, :, :3
    ].astype(np.int16)
    matching_mask = np.sum(color_delta * color_delta, axis=2) <= 75**2
    viewport = editor.viewport()
    viewport_origin = viewport.mapTo(editor, QPoint())
    viewport_left = max(0, viewport_origin.x())
    viewport_right = min(
        backing_store.width(),
        viewport_left + viewport.width(),
    )
    scroll_offset = float(surface._scroll_offset())
    missing: list[str] = []
    for line_index, line in enumerate(layout._snapshot.lines):
        top = max(
            0,
            int(math.floor(viewport_origin.y() + line.top - scroll_offset)),
        )
        bottom = min(
            backing_store.height(),
            int(
                math.ceil(viewport_origin.y() + line.top + line.height - scroll_offset)
            ),
        )
        if bottom <= top:
            continue
        for tile_left in range(viewport_left, viewport_right, _TILE_WIDTH):
            tile_right = min(viewport_right, tile_left + _TILE_WIDTH)
            expected_tile = expected_mask[top:bottom, tile_left:tile_right]
            expected_count = int(np.count_nonzero(expected_tile))
            if expected_count < _MINIMUM_EXPECTED_PIXELS:
                continue
            matching_count = int(
                np.count_nonzero(
                    matching_mask[top:bottom, tile_left:tile_right] & expected_tile
                )
            )
            if matching_count / expected_count < _MINIMUM_RETAINED_RATIO:
                missing.append(
                    f"line={line_index}:x={tile_left}:"
                    f"retained={matching_count}/{expected_count}"
                )
    return tuple(missing)


def _render_projection_reference(editor: Any) -> QImage:
    """Render expected projection content without mutating the live widget."""

    image = QImage(
        max(1, editor.width()),
        max(1, editor.height()),
        QImage.Format.Format_RGBA8888,
    )
    image.fill(0)
    surface = editor._surface
    layout = surface._layout
    viewport = editor.viewport()
    viewport_origin = viewport.mapTo(editor, QPoint())
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.translate(viewport_origin)
        scroll_offset = float(surface._scroll_offset())
        painter.translate(0.0, -scroll_offset)
        painter.setClipRect(QRectF(viewport.rect()).translated(0.0, scroll_offset))
        paint_styles: dict[str, Any] = {}
        selection = surface._selection()
        for line in layout._snapshot.lines:
            for fragment in line.fragments:
                if isinstance(fragment, PromptProjectionTextFragment):
                    layout._painter._paint_text_fragment(
                        painter,
                        fragment,
                        selection=selection,
                        paint_styles=paint_styles,
                    )
    finally:
        painter.end()
    return image


def _rgba_pixels(image: QImage) -> NDArray[np.uint8]:
    """Return an owned height-by-width RGBA array for one logical-size image."""

    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixel_count = converted.width() * converted.height() * 4
    return (
        np.frombuffer(
            converted.bits(),
            dtype=np.uint8,
            count=pixel_count,
        )
        .reshape((converted.height(), converted.width(), 4))
        .copy()
    )


__all__ = ["missing_projection_text_tiles"]
