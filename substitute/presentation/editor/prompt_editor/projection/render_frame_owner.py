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

"""Publish one complete immutable prompt render frame before paint events."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette, QRegion

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptPaintIdentity,
    PromptSourceIdentity,
)

from .caret_layer_owner import PromptCaretRenderLayerOwner
from .caret_render_state import EMPTY_CARET_RENDER_LAYER
from .content_media_state import PromptProjectionContentMediaIdentity
from .content_selection_layer import (
    EMPTY_PROJECTION_SELECTION_LAYER,
    PromptProjectionSelectionLayer,
)
from .diagnostic_render_layer import (
    EMPTY_DIAGNOSTIC_RENDER_LAYER,
    PromptDiagnosticRenderLayer,
)
from .input_method_render_state import (
    EMPTY_INPUT_METHOD_RENDER_LAYER,
    PromptInputMethodRenderLayer,
)
from .metrics import PromptProjectionMetrics
from .paint_input import PromptProjectionPaintInput
from .region_chrome_state import PromptRegionChromeSnapshot
from .render_frame import (
    PromptProjectionContentPaintMode,
    PromptProjectionRenderFrame,
    PromptReorderRenderInstrumentation,
    render_frame_identity,
)
from .reorder_surface_chrome import PromptReorderSurfaceChromeSnapshot
from .search_highlight_layer import (
    EMPTY_SEARCH_HIGHLIGHT_LAYER,
    PromptSearchHighlightLayer,
)
from .source_line_render_state import PromptSourceLineChromeLayer
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .transient_edit_layer_owner import PromptTransientEditRenderLayerOwner
from .transient_edit_render_state import (
    EMPTY_TRANSIENT_EDIT_RENDER_LAYER,
)


class PromptProjectionRenderFrameOwner:
    """Own transient preparation and atomic render-frame publication."""

    def __init__(self) -> None:
        """Create focused transient and caret layer publication owners."""

        self._transient_layers = PromptTransientEditRenderLayerOwner()
        self._caret_layers = PromptCaretRenderLayerOwner()
        self._frame: PromptProjectionRenderFrame | None = None

    @property
    def frame(self) -> PromptProjectionRenderFrame:
        """Return the complete current render frame."""

        if self._frame is None:
            raise RuntimeError("prompt render frame has not been published")
        return self._frame

    def publish(
        self,
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
        diagnostic_layer: PromptDiagnosticRenderLayer,
        input_method_layer: PromptInputMethodRenderLayer,
        overlays: PromptProjectionTransientEditOverlayController,
        freshness_is_stale_safe: bool,
        source_identity: PromptSourceIdentity,
        metrics: PromptProjectionMetrics,
        viewport_rect: QRectF,
        scroll_offset: float,
        device_pixel_ratio: float,
        font: QFont,
        palette: QPalette,
        caret_visible: bool,
        caret_rect: QRectF,
        preview_content_visible_region: QRegion | None,
        reorder_instrumentation: PromptReorderRenderInstrumentation | None,
    ) -> bool:
        """Prepare mode-specific layers and atomically publish their exact frame."""

        preview = (
            content_mode is PromptProjectionContentPaintMode.DIRECT_REORDER_PREVIEW
        )
        if preview:
            resolved_selection = EMPTY_PROJECTION_SELECTION_LAYER
            resolved_search = EMPTY_SEARCH_HIGHLIGHT_LAYER
            resolved_diagnostics = EMPTY_DIAGNOSTIC_RENDER_LAYER
            resolved_input_method = EMPTY_INPUT_METHOD_RENDER_LAYER
            transient_layer = EMPTY_TRANSIENT_EDIT_RENDER_LAYER
            caret_layer = EMPTY_CARET_RENDER_LAYER
            content_visible_region = preview_content_visible_region
        else:
            resolved_selection = selection_layer
            resolved_search = search_layer
            resolved_diagnostics = diagnostic_layer
            resolved_input_method = input_method_layer
            self._transient_layers.prepare(
                overlays=overlays,
                freshness_is_stale_safe=freshness_is_stale_safe,
                source_identity=source_identity,
                metrics=metrics,
                viewport_rect=viewport_rect,
                scroll_offset=scroll_offset,
                font=font,
                palette=palette,
            )
            transient_layer = self._transient_layers.layer
            self._caret_layers.prepare(
                visible=caret_visible and resolved_input_method.key is None,
                rect=caret_rect,
                palette=palette,
            )
            caret_layer = self._caret_layers.layer
            content_visible_region = transient_layer.content_visible_region
        identity = render_frame_identity(
            paint_input=paint_input,
            paint_identity=paint_identity,
            content_media_identity=content_media_identity,
            content_mode=content_mode,
            selection_layer=resolved_selection,
            source_line_layer=source_line_layer,
            region_layer=region_layer,
            reorder_layer=reorder_layer,
            search_layer=resolved_search,
            transient_layer=transient_layer,
            diagnostic_layer=resolved_diagnostics,
            input_method_layer=resolved_input_method,
            caret_layer=caret_layer,
            reorder_instrumentation=reorder_instrumentation,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=device_pixel_ratio,
        )
        if self._frame is not None and self._frame.identity == identity:
            return False
        self._frame = PromptProjectionRenderFrame(
            identity=identity,
            paint_input=paint_input,
            paint_identity=paint_identity,
            content_media_identity=content_media_identity,
            content_mode=content_mode,
            selection_layer=resolved_selection,
            source_line_layer=source_line_layer,
            region_layer=region_layer,
            reorder_layer=reorder_layer,
            search_layer=resolved_search,
            transient_layer=transient_layer,
            diagnostic_layer=resolved_diagnostics,
            input_method_layer=resolved_input_method,
            caret_layer=caret_layer,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=max(1.0, device_pixel_ratio),
            content_visible_region=content_visible_region,
            reorder_instrumentation=reorder_instrumentation,
        )
        return True


__all__ = ["PromptProjectionRenderFrameOwner"]
