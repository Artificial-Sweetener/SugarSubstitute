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

from substitute.presentation.editor.prompt_editor.projection.painter import (
    PromptProjectionPainter,
)

_TILE_WIDTH = 96
_MINIMUM_EXPECTED_PIXELS = 8
_MINIMUM_OPAQUE_TEXT_ALPHA = 200
_MINIMUM_RETAINED_RATIO = 0.15
_MINIMUM_VISIBLE_LINE_RATIO = 0.5
_MINIMUM_LOCAL_CONTRAST = 40


def missing_projection_text_tiles(
    editor: Any,
    backing_store: QImage,
) -> tuple[str, ...]:
    """Return visible layout tiles whose expected glyph pixels are absent."""

    surface = editor._runtime.projection.surface
    frame = surface._layout.frame
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
    matching_mask |= local_contrast_mask(actual_rgba[:, :, :3])
    viewport = editor.viewport()
    viewport_origin = viewport.mapTo(editor, QPoint())
    viewport_left = max(0, viewport_origin.x())
    viewport_right = min(
        backing_store.width(),
        viewport_left + viewport.width(),
    )
    viewport_top = max(0, viewport_origin.y())
    viewport_bottom = min(
        backing_store.height(),
        viewport_top + viewport.height(),
    )
    scroll_offset = float(surface._scroll_offset())
    missing: list[str] = []
    for line_index, line in enumerate(frame.output.snapshot.lines):
        visible_band = visible_projection_line_band(
            viewport_top=viewport_top,
            viewport_bottom=viewport_bottom,
            line_top=viewport_origin.y() + line.top - scroll_offset,
            line_height=line.height,
        )
        if visible_band is None:
            continue
        top, bottom = visible_band
        for tile_left in range(viewport_left, viewport_right, _TILE_WIDTH):
            tile_right = min(viewport_right, tile_left + _TILE_WIDTH)
            expected_tile = expected_mask[top:bottom, tile_left:tile_right]
            expected_alpha = expected_rgba[top:bottom, tile_left:tile_right, 3]
            if not has_comparable_text_pixels(expected_alpha):
                continue
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


def has_comparable_text_pixels(expected_alpha: NDArray[np.uint8]) -> bool:
    """Return whether a tile contains enough opaque pixels to represent glyphs."""

    return bool(
        np.count_nonzero(expected_alpha >= _MINIMUM_OPAQUE_TEXT_ALPHA)
        >= _MINIMUM_EXPECTED_PIXELS
    )


def local_contrast_mask(actual_rgb: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Return pixels bordering visible color transitions such as glyph edges."""

    rgb = actual_rgb.astype(np.int16)
    contrast = np.zeros(rgb.shape[:2], dtype=np.bool_)
    horizontal = (
        np.max(np.abs(rgb[:, 1:] - rgb[:, :-1]), axis=2) >= _MINIMUM_LOCAL_CONTRAST
    )
    contrast[:, 1:] |= horizontal
    contrast[:, :-1] |= horizontal
    vertical = (
        np.max(np.abs(rgb[1:, :] - rgb[:-1, :]), axis=2) >= _MINIMUM_LOCAL_CONTRAST
    )
    contrast[1:, :] |= vertical
    contrast[:-1, :] |= vertical
    return contrast


def visible_projection_line_band(
    *,
    viewport_top: int,
    viewport_bottom: int,
    line_top: float,
    line_height: float,
) -> tuple[int, int] | None:
    """Return a stable pixel band for a meaningfully visible projection line."""

    if line_height <= 0.0 or viewport_bottom <= viewport_top:
        return None
    line_bottom = line_top + line_height
    visible_top = max(float(viewport_top), line_top)
    visible_bottom = min(float(viewport_bottom), line_bottom)
    visible_height = visible_bottom - visible_top
    if visible_height < line_height * _MINIMUM_VISIBLE_LINE_RATIO:
        return None
    top = max(viewport_top, int(math.floor(line_top)))
    bottom = min(viewport_bottom, int(math.ceil(line_bottom)))
    return (top, bottom) if bottom > top else None


def _render_projection_reference(editor: Any) -> QImage:
    """Render expected projection content without mutating the live widget."""

    image = QImage(
        max(1, editor.width()),
        max(1, editor.height()),
        QImage.Format.Format_RGBA8888,
    )
    image.fill(0)
    surface = editor._runtime.projection.surface
    frame = surface._layout.frame
    viewport = editor.viewport()
    viewport_origin = viewport.mapTo(editor, QPoint())
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.translate(viewport_origin)
        scroll_offset = float(surface._scroll_offset())
        PromptProjectionPainter().draw(
            painter,
            paint_input=frame.paint_input,
            selection_layer=surface._selection_layer_owner.layer,
            scroll_offset=scroll_offset,
            clip_rect=QRectF(viewport.rect()),
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


__all__ = [
    "has_comparable_text_pixels",
    "local_contrast_mask",
    "missing_projection_text_tiles",
    "visible_projection_line_band",
]
