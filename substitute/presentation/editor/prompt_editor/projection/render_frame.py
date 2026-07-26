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

"""Define the complete immutable prompt render frame consumed by composition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QRectF
from PySide6.QtGui import QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptPaintIdentity,
)

from .caret_render_state import PromptCaretRenderLayer
from .content_media_state import PromptProjectionContentMediaIdentity
from .content_selection_layer import PromptProjectionSelectionLayer
from .diagnostic_render_layer import PromptDiagnosticRenderLayer
from .input_method_render_state import PromptInputMethodRenderLayer
from .paint_input import PromptProjectionPaintInput
from .region_chrome_state import PromptRegionChromeSnapshot
from .reorder_surface_chrome import PromptReorderSurfaceChromeSnapshot
from .search_highlight_layer import PromptSearchHighlightLayer
from .source_line_render_state import PromptSourceLineChromeLayer
from .transient_edit_render_state import PromptTransientEditRenderLayer


class PromptProjectionContentPaintMode(Enum):
    """Select one explicit projection-content cache policy."""

    CACHED = "cached"
    DIRECT_REORDER_PREVIEW = "direct_reorder_preview"
    DIRECT_AUTOCOMPLETE_PREVIEW = "direct_autocomplete_preview"
    DIRECT_UNPREPARED = "direct_unprepared"


@dataclass(frozen=True, slots=True)
class PromptProjectionRenderFrameIdentity:
    """Bind one render frame to every upstream immutable publication."""

    layout_snapshot_identity: int
    paint_input_identity: int
    paint_identity: PromptPaintIdentity | None
    content_media_identity: PromptProjectionContentMediaIdentity
    viewport: tuple[int, int, int, int]
    scroll_offset: int
    device_pixel_ratio_x100: int
    content_mode: PromptProjectionContentPaintMode
    selection_layer_identity: int
    source_line_layer_identity: int
    region_layer_identity: int | None
    reorder_layer_identity: int | None
    search_layer_identity: int
    transient_layer_identity: int
    diagnostic_layer_identity: int
    input_method_layer_identity: int
    caret_layer_identity: int
    reorder_instrumentation: PromptReorderRenderInstrumentation | None


@dataclass(frozen=True, slots=True)
class PromptReorderRenderInstrumentation:
    """Capture stable preview context before the compositor enters paint."""

    gesture_id: int | None
    event_id: int | None
    line_count: int
    text_fragment_count: int
    inline_object_count: int


@dataclass(frozen=True, slots=True)
class PromptProjectionRenderFrame:
    """Contain every prepared layer and viewport input for one paint revision."""

    identity: PromptProjectionRenderFrameIdentity
    paint_input: PromptProjectionPaintInput
    paint_identity: PromptPaintIdentity | None
    content_media_identity: PromptProjectionContentMediaIdentity
    content_mode: PromptProjectionContentPaintMode
    selection_layer: PromptProjectionSelectionLayer
    source_line_layer: PromptSourceLineChromeLayer
    region_layer: PromptRegionChromeSnapshot | None
    reorder_layer: PromptReorderSurfaceChromeSnapshot | None
    search_layer: PromptSearchHighlightLayer
    transient_layer: PromptTransientEditRenderLayer
    diagnostic_layer: PromptDiagnosticRenderLayer
    input_method_layer: PromptInputMethodRenderLayer
    caret_layer: PromptCaretRenderLayer
    viewport_rect: QRectF
    scroll_offset: float
    device_pixel_ratio: float
    content_visible_region: QRegion | None
    reorder_instrumentation: PromptReorderRenderInstrumentation | None = None

    def __post_init__(self) -> None:
        """Detach retained mutable Qt viewport and region values."""

        object.__setattr__(self, "viewport_rect", QRectF(self.viewport_rect))
        if self.content_visible_region is not None:
            object.__setattr__(
                self,
                "content_visible_region",
                QRegion(self.content_visible_region),
            )


def render_frame_identity(
    *,
    paint_input: PromptProjectionPaintInput,
    paint_identity: PromptPaintIdentity | None,
    content_media_identity: PromptProjectionContentMediaIdentity,
    content_mode: PromptProjectionContentPaintMode,
    selection_layer: PromptProjectionSelectionLayer,
    source_line_layer: PromptSourceLineChromeLayer,
    region_layer: PromptRegionChromeSnapshot | None,
    reorder_layer: PromptReorderSurfaceChromeSnapshot | None,
    search_layer: PromptSearchHighlightLayer,
    transient_layer: PromptTransientEditRenderLayer,
    diagnostic_layer: PromptDiagnosticRenderLayer,
    input_method_layer: PromptInputMethodRenderLayer,
    caret_layer: PromptCaretRenderLayer,
    reorder_instrumentation: PromptReorderRenderInstrumentation | None,
    viewport_rect: QRectF,
    scroll_offset: float,
    device_pixel_ratio: float,
) -> PromptProjectionRenderFrameIdentity:
    """Build an allocation-bounded identity from upstream immutable layers."""

    return PromptProjectionRenderFrameIdentity(
        layout_snapshot_identity=id(paint_input.layout_snapshot),
        paint_input_identity=id(paint_input),
        paint_identity=paint_identity,
        content_media_identity=content_media_identity,
        viewport=_rect_key(viewport_rect),
        scroll_offset=_coordinate(scroll_offset),
        device_pixel_ratio_x100=_coordinate(max(1.0, device_pixel_ratio)),
        content_mode=content_mode,
        selection_layer_identity=id(selection_layer),
        source_line_layer_identity=id(source_line_layer),
        region_layer_identity=None if region_layer is None else id(region_layer),
        reorder_layer_identity=None if reorder_layer is None else id(reorder_layer),
        search_layer_identity=id(search_layer),
        transient_layer_identity=id(transient_layer),
        diagnostic_layer_identity=id(diagnostic_layer),
        input_method_layer_identity=id(input_method_layer),
        caret_layer_identity=id(caret_layer),
        reorder_instrumentation=reorder_instrumentation,
    )


def _rect_key(rect: QRectF) -> tuple[int, int, int, int]:
    """Quantize one viewport rectangle for exact render identity."""

    return (
        _coordinate(rect.x()),
        _coordinate(rect.y()),
        _coordinate(rect.width()),
        _coordinate(rect.height()),
    )


def _coordinate(value: float) -> int:
    """Quantize one presentation coordinate without losing subpixel identity."""

    return int(round(value * 100.0))


__all__ = [
    "PromptProjectionContentPaintMode",
    "PromptProjectionRenderFrame",
    "PromptProjectionRenderFrameIdentity",
    "PromptReorderRenderInstrumentation",
    "render_frame_identity",
]
