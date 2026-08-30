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

"""Observe rendering contracts owned by the prompt reorder surface."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QLineF, QPoint, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.layout.models import (
    PromptProjectionTextFragment,
)
from tests.support.prompt_editor.real_shell.models import (
    PromptFieldHandle,
    PromptReorderChipChromeSnapshot,
    PromptReorderRenderedLayoutSnapshot,
    PromptSourceLineChromeRenderProbe,
)
from tests.support.qt.semantic_wait import wait_for_queued_qt_turn


def capture_source_line_chrome(
    editor: PromptEditor,
    *,
    label: str,
) -> PromptSourceLineChromeRenderProbe:
    """Render source-line chrome headlessly using active preview geometry."""

    wait_for_queued_qt_turn()
    surface = cast(Any, editor)._surface
    preview_frame = surface._reorder_preview_projection.preview_frame
    frame = preview_frame if preview_frame is not None else surface._layout.frame
    viewport = surface.viewport()
    image = QImage(
        max(1, editor.width()),
        max(1, editor.height()),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(0)
    painter = QPainter(image)
    try:
        editor.render(painter, QPoint(0, 0))
    finally:
        painter.end()

    source_lines = surface._source_line_chrome.source_line_rects(
        geometry=frame.geometry,
        viewport_rect=QRectF(viewport.rect()),
        scroll_offset=surface._scroll_offset(),
    )
    sample_x = max(0, viewport.width() - 4)
    line_colors: list[tuple[int, tuple[int, int, int, int]]] = []
    for source_line in source_lines:
        viewport_y = max(
            0, min(viewport.height() - 1, int(source_line.rect.center().y()))
        )
        editor_position = viewport.mapTo(editor, QPoint(sample_x, viewport_y))
        color = image.pixelColor(editor_position)
        line_colors.append(
            (
                source_line.line_index,
                (color.red(), color.green(), color.blue(), color.alpha()),
            )
        )
    segment_overlay = editor._segment_overlay
    return PromptSourceLineChromeRenderProbe(
        label=label,
        reorder_overlay_active=bool(
            isinstance(segment_overlay, QWidget) and segment_overlay.isVisible()
        ),
        projection_preview_active=preview_frame is not None,
        line_colors=tuple(line_colors),
    )


def capture_reorder_layout(
    field: PromptFieldHandle,
    *,
    label: str,
) -> PromptReorderRenderedLayoutSnapshot:
    """Capture the exact preview-or-live frame currently rendered by the surface."""

    surface = cast(Any, field.editor)._surface
    preview_frame = surface._reorder_preview_projection.preview_frame
    frame = preview_frame if preview_frame is not None else surface._layout.frame
    output = frame.output
    snapshot = output.snapshot
    fragments: list[tuple[str, str, tuple[float, float, float, float]]] = []
    ordered_fragments = sorted(
        (*snapshot.text_fragments, *snapshot.inline_object_fragments),
        key=lambda fragment: (
            fragment.rect.top(),
            fragment.rect.left(),
            fragment.projection_start,
        ),
    )
    for fragment in ordered_fragments:
        if isinstance(fragment, PromptProjectionTextFragment):
            fragment_kind, fragment_value = "text", fragment.text
        else:
            fragment_kind, fragment_value = "inline", fragment.renderer_key
        fragments.append(
            (fragment_kind, fragment_value, rectangle_tuple(fragment.rect))
        )
    content_size = snapshot.content_size
    render_frame = surface._render_frame_owner.frame
    region_layer = render_frame.region_layer
    return PromptReorderRenderedLayoutSnapshot(
        label=label,
        preview_active=preview_frame is not None,
        source_text=output.projection_document.source_text,
        projection_text=output.projection_document.projection_text,
        content_size=(float(content_size.width()), float(content_size.height())),
        line_rects=tuple(rectangle_tuple(line.rect) for line in snapshot.lines),
        fragments=tuple(fragments),
        region_divider_lines=(
            ()
            if region_layer is None
            else tuple(line_tuple(line) for line in region_layer.divider_lines)
        ),
        region_rail_lines=(
            ()
            if region_layer is None
            else tuple(line_tuple(line) for line in region_layer.rail_lines)
        ),
        region_stroke_lines=(
            ()
            if region_layer is None
            else tuple(
                line_tuple(line)
                for stroke in region_layer.strokes
                for line in stroke.lines
            )
        ),
    )


def capture_reorder_chip_chrome(
    field: PromptFieldHandle,
    *,
    segment_index: int,
    label: str,
) -> PromptReorderChipChromeSnapshot:
    """Capture the paint owners and border style for one semantic reorder chip."""

    overlay = cast(Any, field.editor)._segment_overlay
    publication = overlay._render_publication.publication
    overlay_state = publication.overlay_state
    overlay_chips = (
        overlay_state.preview_chips
        if overlay_state.preview_active
        else overlay_state.live_chips
    )
    owners_and_styles = [
        ("surface", chip.style)
        for chip in publication.surface.chips
        if chip.segment_index == segment_index
    ]
    owners_and_styles.extend(
        ("overlay", chip.style)
        for chip in overlay_chips
        if chip.segment_index == segment_index
    )
    animation = overlay._animation_presentation.publication
    return PromptReorderChipChromeSnapshot(
        label=label,
        segment_index=segment_index,
        paint_owners=tuple(owner for owner, _style in owners_and_styles),
        border_colors=tuple(
            (
                style.border_color.red(),
                style.border_color.green(),
                style.border_color.blue(),
                style.border_color.alpha(),
            )
            for _owner, style in owners_and_styles
        ),
        animation_override_active=segment_index in animation.paint_rects_by_index,
        unsafe_transient=segment_index in publication.unsafe_transient_indices,
    )


def rectangle_tuple(rectangle: QRectF) -> tuple[float, float, float, float]:
    """Return one QRectF as stable diagnostic coordinates."""

    return (
        float(rectangle.x()),
        float(rectangle.y()),
        float(rectangle.width()),
        float(rectangle.height()),
    )


def line_tuple(line: QLineF) -> tuple[float, float, float, float]:
    """Return one QLineF as stable diagnostic coordinates."""

    return (float(line.x1()), float(line.y1()), float(line.x2()), float(line.y2()))
