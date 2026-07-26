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

"""Compose prepared prompt render layers in one deterministic z-order."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter

from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptPaintIdentity,
)

from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    begin_prompt_editor_work,
    complete_prompt_editor_result_work,
    complete_prompt_editor_work,
    prompt_editor_paint_cache_event,
)

from .caret_renderer import PromptCaretRenderer
from .diagnostic_renderer import PromptDiagnosticRenderer
from .input_method_renderer import PromptInputMethodRenderer
from .observability import log_reorder_drag_timing, reorder_drag_started_at
from .paint_cache import (
    PromptProjectionContentCacheSnapshot,
    PromptProjectionPaintCache,
)
from .region_chrome_renderer import PromptRegionChromeRenderer
from .render_frame import (
    PromptProjectionContentPaintMode,
    PromptProjectionRenderFrame,
)
from .reorder_surface_chrome import PromptReorderSurfaceChromePainter
from .search_highlight_renderer import PromptSearchHighlightRenderer
from .source_line_renderer import PromptSourceLineChromeRenderer
from .transient_edit_renderer import PromptTransientEditRenderer


class PromptProjectionRenderCompositor:
    """Own the complete prepared-layer order and projection cache selection."""

    def __init__(self) -> None:
        """Create the one content-cache owner and stateless render sinks."""

        self._content_cache = PromptProjectionPaintCache()
        self._source_lines = PromptSourceLineChromeRenderer()
        self._regions = PromptRegionChromeRenderer()
        self._reorder = PromptReorderSurfaceChromePainter()
        self._search = PromptSearchHighlightRenderer()
        self._transient = PromptTransientEditRenderer()
        self._diagnostics = PromptDiagnosticRenderer()
        self._input_method = PromptInputMethodRenderer()
        self._caret = PromptCaretRenderer()

    @property
    def content_cache_snapshot(self) -> PromptProjectionContentCacheSnapshot:
        """Return immutable content-cache state for diagnostics and tests."""

        return self._content_cache.snapshot

    def discard_stale_content_cache(
        self, paint_identity: PromptPaintIdentity | None
    ) -> None:
        """Release cached pixels that cannot serve the frame about to publish."""

        self._content_cache.discard_if_stale(paint_identity)

    def draw(
        self,
        painter: QPainter,
        frame: PromptProjectionRenderFrame,
        *,
        event_clip: QRectF,
    ) -> str:
        """Draw one complete frame without discovering mutable editor state."""

        paint_work_started_at = begin_prompt_editor_work()
        instrumentation = frame.reorder_instrumentation
        preview_started_at = (
            reorder_drag_started_at() if instrumentation is not None else None
        )
        self._source_lines.draw(painter, frame.source_line_layer)
        self._regions.draw(
            painter,
            frame.region_layer,
            scroll_offset=frame.scroll_offset,
        )
        if frame.reorder_layer is not None:
            self._reorder.paint(painter, frame.reorder_layer)
        self._search.draw(
            painter,
            frame.search_layer,
            viewport_rect=frame.viewport_rect,
            scroll_offset=frame.scroll_offset,
        )
        content_work_started_at = begin_prompt_editor_work()
        content_result = self.draw_content(
            painter,
            frame,
            event_clip=event_clip,
        )
        complete_prompt_editor_result_work(
            prompt_editor_paint_cache_event,
            content_result,
            started_at=content_work_started_at,
        )
        if instrumentation is not None and preview_started_at is not None:
            log_reorder_drag_timing(
                "surface.paint.preview",
                started_at=preview_started_at,
                gesture_id=instrumentation.gesture_id,
                event_id=instrumentation.event_id,
                viewport_width=frame.viewport_rect.width(),
                viewport_height=frame.viewport_rect.height(),
                scroll_offset=frame.scroll_offset,
                preview_active=True,
                line_count=instrumentation.line_count,
                text_fragment_count=instrumentation.text_fragment_count,
                inline_object_count=instrumentation.inline_object_count,
                clip_width=frame.viewport_rect.width(),
                clip_height=frame.viewport_rect.height(),
            )
        self._transient.draw_insertion(painter, frame.transient_layer)
        self._diagnostics.draw(painter, layer=frame.diagnostic_layer)
        self._transient.draw_deletion(painter, frame.transient_layer)
        self._input_method.draw(painter, frame.input_method_layer)
        self._caret.draw(painter, frame.caret_layer)
        complete_prompt_editor_work(
            PromptEditorWorkEvent.SURFACE_PAINT_EVENT,
            started_at=paint_work_started_at,
        )
        return content_result

    def draw_content(
        self,
        painter: QPainter,
        frame: PromptProjectionRenderFrame,
        *,
        event_clip: QRectF,
    ) -> str:
        """Apply one explicit cache policy to prepared projection content."""

        mode = frame.content_mode
        if mode is not PromptProjectionContentPaintMode.CACHED:
            clip_rect = (
                frame.viewport_rect
                if mode is PromptProjectionContentPaintMode.DIRECT_REORDER_PREVIEW
                else event_clip
            )
            self._content_cache.paint_direct(
                painter,
                paint_input=frame.paint_input,
                selection_layer=frame.selection_layer,
                scroll_offset=frame.scroll_offset,
                clip_rect=clip_rect,
                excluded_region=frame.content_visible_region,
            )
            if mode is PromptProjectionContentPaintMode.DIRECT_UNPREPARED:
                return "bypass_unprepared"
            return "preview"
        paint_identity = frame.paint_identity
        if paint_identity is None:
            raise ValueError("cached projection content requires a paint identity")
        return self._content_cache.paint_projection_content(
            painter,
            paint_input=frame.paint_input,
            selection_layer=frame.selection_layer,
            scroll_offset=frame.scroll_offset,
            clip_rect=event_clip,
            viewport_rect=frame.viewport_rect,
            excluded_region=frame.content_visible_region,
            paint_identity=paint_identity,
            media_identity=frame.content_media_identity,
            device_pixel_ratio=frame.device_pixel_ratio,
        )


__all__ = ["PromptProjectionRenderCompositor"]
