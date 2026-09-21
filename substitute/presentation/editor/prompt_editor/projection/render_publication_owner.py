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

"""Own complete prompt render-frame input selection and publication."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import QWidget

from ..qt_lifecycle import qt_object_is_alive
from .content_media_owner import PromptProjectionContentMediaOwner
from .content_selection_owner import PromptProjectionSelectionLayerOwner
from .diagnostic_layer_owner import PromptDiagnosticLayerOwner
from .edit_to_frame import PromptLayoutEditToFrameCoordinator
from .frame_state import PromptProjectionEditorState
from .freshness_controller import PromptProjectionFreshnessController
from .input_method_controller import PromptInputMethodController
from .prepared_frame import PromptProjectionPreparedFrame
from .region_chrome import PromptRegionChrome
from .render_frame import (
    PromptProjectionContentPaintMode,
    PromptReorderRenderInstrumentation,
)
from .render_frame_owner import PromptProjectionRenderFrameOwner
from .reorder_preview_projection_owner import PromptReorderPreviewProjectionOwner
from .reorder_surface_chrome import PromptReorderSurfaceChromeSnapshot
from .reorder_surface_visual_state import PromptReorderSurfaceVisualStateOwner
from .search_highlight_owner import PromptSearchHighlightLayerOwner
from .session import PromptProjectionSession
from .source_line_chrome import PromptSourceLineChrome
from .transient_edit_overlays import PromptProjectionTransientEditOverlayController
from .undo_payload import PromptProjectionUndoPayload


class PromptProjectionRenderPublicationOwner:
    """Resolve mutable projection state into one atomic immutable render frame."""

    def __init__(
        self,
        *,
        surface: QWidget,
        viewport: QWidget,
        layout: PromptLayoutEditToFrameCoordinator,
        editor_state: PromptProjectionEditorState,
        session: PromptProjectionSession,
        reorder_preview: PromptReorderPreviewProjectionOwner,
        input_method: PromptInputMethodController[PromptProjectionUndoPayload],
        content_media: PromptProjectionContentMediaOwner,
        selection_layer: PromptProjectionSelectionLayerOwner,
        source_line_chrome: PromptSourceLineChrome,
        region_chrome: PromptRegionChrome,
        reorder_visual_state: PromptReorderSurfaceVisualStateOwner,
        search_highlight: PromptSearchHighlightLayerOwner,
        diagnostics: PromptDiagnosticLayerOwner,
        transient_overlays: PromptProjectionTransientEditOverlayController,
        freshness: PromptProjectionFreshnessController,
        frame_owner: PromptProjectionRenderFrameOwner,
        active_frame: Callable[[], PromptProjectionPreparedFrame],
        cursor_position: Callable[[], int],
        focus_active: Callable[[], bool],
        scroll_offset: Callable[[], float],
        should_paint_caret: Callable[[], bool],
        current_caret_rect: Callable[[], QRectF],
        preview_visible_region: Callable[[], QRegion | None],
        reorder_preview_generation: Callable[[], int | None],
    ) -> None:
        """Retain every owner needed to publish one internally consistent frame."""
        self._surface = surface
        self._viewport = viewport
        self._layout = layout
        self._editor_state = editor_state
        self._session = session
        self._reorder_preview = reorder_preview
        self._input_method = input_method
        self._content_media = content_media
        self._selection_layer = selection_layer
        self._source_line_chrome = source_line_chrome
        self._region_chrome = region_chrome
        self._reorder_visual_state = reorder_visual_state
        self._search_highlight = search_highlight
        self._diagnostics = diagnostics
        self._transient_overlays = transient_overlays
        self._freshness = freshness
        self._frame_owner = frame_owner
        self._active_frame = active_frame
        self._cursor_position = cursor_position
        self._focus_active = focus_active
        self._scroll_offset = scroll_offset
        self._should_paint_caret = should_paint_caret
        self._current_caret_rect = current_caret_rect
        self._preview_visible_region = preview_visible_region
        self._reorder_preview_generation = reorder_preview_generation

    def viewport_scrolled(self) -> None:
        """Refresh every viewport-bound layer before publishing one frame."""

        self._selection_layer.refresh()
        self._diagnostics.refresh(reason="viewport_scrolled")
        self._prepare_source_line_chrome()
        self._prepare_search_highlight()
        self.publish()

    def visual_style_changed(self) -> None:
        """Republish style-sensitive input-method and frame presentation."""

        self.publish()

    def source_line_configuration_changed(self) -> None:
        """Publish newly configured source-line commands atomically."""

        self._prepare_source_line_chrome()
        self.publish()

    def search_changed(self) -> None:
        """Prepare current search commands and publish their exact frame."""

        self._prepare_search_highlight()
        self.publish()

    def search_cleared(self) -> None:
        """Clear search commands and publish the empty layer atomically."""

        self._search_highlight.clear()
        self.publish()

    def source_changed(self, *, clear_diagnostic_fragment_cache: bool) -> None:
        """Invalidate diagnostic geometry when source lineage requires it."""

        if clear_diagnostic_fragment_cache:
            self._diagnostics.clear_fragment_cache(reason="source_changed")

    def caret_changed(self) -> None:
        """Refresh caret-dependent layers before caret-frame publication."""

        self._selection_layer.refresh()
        self._diagnostics.refresh(reason="selection_changed")
        self._prepare_source_line_chrome()

    def deferred_caret_changed(self) -> None:
        """Refresh layers valid while source caret geometry remains deferred."""

        self._selection_layer.refresh()
        self._diagnostics.refresh(reason="selection_changed")

    def viewport_resized(self) -> None:
        """Discard diagnostic fragments tied to the previous viewport size."""

        self._diagnostics.clear_fragment_cache(reason="resize")

    def focus_changed(self) -> None:
        """Prepare focus-sensitive chrome and publish its exact frame."""

        self._prepare_source_line_chrome()
        self.publish()

    def prepare_focus_chrome(self) -> None:
        """Prepare focus-sensitive chrome before the caret owner publishes."""

        self._prepare_source_line_chrome()

    def diagnostic_layer_changed(self) -> None:
        """Publish a changed diagnostic layer before requesting its repaint."""

        self.publish()
        self._viewport.update()

    def projection_rebuilt(self, *, invalidation_reason: str) -> None:
        """Discard diagnostic fragments tied to replaced projection geometry."""

        self._diagnostics.clear_fragment_cache(reason=invalidation_reason)

    def layout_synchronized(self) -> None:
        """Refresh all layout-bound layers before publishing one frame."""

        self._selection_layer.refresh()
        self._diagnostics.refresh(reason="layout_synchronized")
        self._prepare_source_line_chrome()
        self._prepare_search_highlight()
        self.publish()

    def publish(self) -> bool:
        """Select live or preview inputs and atomically publish the render frame."""
        if not qt_object_is_alive(self._surface) or not qt_object_is_alive(
            self._viewport
        ):
            return False
        viewport_rect = QRectF(self._viewport.rect())
        scroll_offset = self._scroll_offset()
        preview_frame = self._reorder_preview.preview_frame
        paint_snapshot = self._editor_state.current_paint
        if preview_frame is not None:
            paint_input = preview_frame.paint_input
            metrics = preview_frame.output.configuration.metrics
            paint_identity = None
            content_mode = PromptProjectionContentPaintMode.DIRECT_REORDER_PREVIEW
            reorder_mode = "preview"
            preview_visible_region = self._preview_visible_region()
            preview_state = self._reorder_preview.preview_state
            reorder_instrumentation = PromptReorderRenderInstrumentation(
                gesture_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_gesture_id
                ),
                event_id=(
                    None
                    if preview_state is None
                    else preview_state.instrumentation_event_id
                ),
                line_count=preview_frame.output.snapshot.line_count(),
                text_fragment_count=(
                    preview_frame.output.snapshot.text_fragment_count()
                ),
                inline_object_count=(
                    preview_frame.output.snapshot.inline_object_fragment_count()
                ),
            )
        else:
            paint_input = self._layout.frame.paint_input
            metrics = self._layout.frame.output.configuration.metrics
            paint_identity = None if paint_snapshot is None else paint_snapshot.identity
            if self._session.autocomplete_preview is not None:
                content_mode = (
                    PromptProjectionContentPaintMode.DIRECT_AUTOCOMPLETE_PREVIEW
                )
            elif paint_identity is None:
                content_mode = PromptProjectionContentPaintMode.DIRECT_UNPREPARED
            else:
                content_mode = PromptProjectionContentPaintMode.CACHED
            reorder_mode = "live"
            preview_visible_region = None
            reorder_instrumentation = None
        self._input_method.refresh_render_layer()
        caret_visible = (
            preview_frame is None
            and not self._input_method.is_composing
            and self._should_paint_caret()
        )
        caret_rect = self._current_caret_rect() if caret_visible else QRectF()
        return self._frame_owner.publish(
            paint_input=paint_input,
            paint_identity=paint_identity,
            content_media_identity=self._content_media.identity,
            content_mode=content_mode,
            selection_layer=self._selection_layer.layer,
            source_line_layer=self._source_line_chrome.layer,
            region_layer=self._region_chrome.active_snapshot,
            reorder_layer=self._fresh_reorder_surface_chrome(reorder_mode),
            search_layer=self._search_highlight.layer,
            diagnostic_layer=self._diagnostics.layer,
            input_method_layer=self._input_method.render_layer,
            overlays=self._transient_overlays,
            freshness_is_stale_safe=self._freshness.has_stale_projection_geometry(),
            source_identity=self._editor_state.source_identity,
            metrics=metrics,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
            device_pixel_ratio=float(self._viewport.devicePixelRatioF()),
            font=self._surface.font(),
            palette=self._surface.palette(),
            caret_visible=caret_visible,
            caret_rect=caret_rect,
            preview_content_visible_region=preview_visible_region,
            reorder_instrumentation=reorder_instrumentation,
        )

    def _prepare_source_line_chrome(self) -> None:
        """Prepare source-line commands against the active frame and viewport."""

        frame = self._active_frame()
        self._source_line_chrome.prepare(
            geometry=frame.geometry,
            geometry_identity=id(frame.output.snapshot),
            viewport_rect=QRectF(self._viewport.rect()),
            scroll_offset=self._scroll_offset(),
            cursor_position=self._cursor_position(),
            focus_active=self._focus_active(),
        )

    def _prepare_search_highlight(self) -> None:
        """Prepare search commands against the current layout and viewport."""

        layout_snapshot = self._editor_state.layout
        if (
            layout_snapshot is None
            or layout_snapshot.geometry is not self._layout.frame.output.snapshot
            or not self._session.search_match_ranges
        ):
            self._search_highlight.clear()
            return
        self._search_highlight.prepare(
            geometry=self._layout.frame.geometry,
            layout_identity=layout_snapshot.identity,
            match_ranges=self._session.search_match_ranges,
            active_match_index=self._session.active_search_match_index,
            palette=self._surface.palette(),
        )

    def _fresh_reorder_surface_chrome(
        self,
        mode: str,
    ) -> PromptReorderSurfaceChromeSnapshot | None:
        """Return reorder chrome only when it matches the pending render frame."""
        snapshot = self._reorder_visual_state.state.chrome_snapshot
        if snapshot is None or not snapshot.matches(
            source_revision=self._editor_state.source.source_revision,
            viewport_rect=self._viewport.rect(),
            scroll_offset=int(round(self._scroll_offset())),
            preview_generation=(
                self._reorder_preview_generation() if mode == "preview" else None
            ),
            mode=mode,
        ):
            return None
        return snapshot


__all__ = ["PromptProjectionRenderPublicationOwner"]
