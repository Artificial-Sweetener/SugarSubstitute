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

"""Own atomic publication of prepared prompt reorder preview projections."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)

from .applicator import PromptProjectionApplicator
from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_preview import PromptReorderPreviewState, PromptReorderProjectionSnapshot
from .reorder_preview_frame_builder import PromptReorderPreviewFrameBuilder
from .reorder_preview_frame_cache import PromptReorderPreviewFrameCache
from .reorder_preview_layout_builder import PromptReorderReusablePreviewLayout
from .reorder_preview_projection_contracts import (
    PromptReorderPreviewProjectionContext,
    PromptReorderPreviewProjectionInvalidation,
    PromptReorderPreviewProjectionPublication,
)
from .reorder_preview_projection_metrics import (
    PromptReorderPreviewProjectionMetrics,
)


class PromptReorderPreviewProjectionOwner:
    """Publish one coherent preview/base-frame state for a projection surface."""

    def __init__(
        self,
        *,
        projection_applicator: PromptProjectionApplicator,
        thumbnail_cache: PromptLoraThumbnailCache,
        cache_limit: int = 16,
    ) -> None:
        """Create focused build, cache, metric, and publication owners."""

        self._metrics = PromptReorderPreviewProjectionMetrics()
        self._frame_builder = PromptReorderPreviewFrameBuilder(
            projection_applicator=projection_applicator,
            thumbnail_cache=thumbnail_cache,
            metrics=self._metrics,
        )
        self._frame_cache = PromptReorderPreviewFrameCache(
            metrics=self._metrics,
            limit=cache_limit,
        )
        self._publication = PromptReorderPreviewProjectionPublication()

    @property
    def preview_state(self) -> PromptReorderPreviewState | None:
        """Return the active display-only preview request."""

        return self._publication.preview_state

    @property
    def preview_document(self) -> PromptProjectionDocument | None:
        """Return the atomically published preview document."""

        return self._publication.preview_document

    @property
    def preview_frame(self) -> PromptProjectionPreparedFrame | None:
        """Return the atomically published prepared preview frame."""

        return self._publication.preview_frame

    @property
    def base_drag_document(self) -> PromptProjectionDocument | None:
        """Return the atomically published stable drag document."""

        return self._publication.base_drag_document

    @property
    def base_drag_frame(self) -> PromptProjectionPreparedFrame | None:
        """Return the atomically published stable prepared drag frame."""

        return self._publication.base_drag_frame

    def is_active(self) -> bool:
        """Return whether a preview publication suppresses live paint."""

        return self._publication.is_active

    def set_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
        *,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
        live_projection_document: PromptProjectionDocument | None = None,
        live_projection_frame: PromptProjectionPreparedFrame | None = None,
    ) -> PromptReorderPreviewProjectionInvalidation:
        """Build and atomically publish the requested preview projection."""

        publication, invalidation = self._build_publication(
            preview_state=preview_state,
            context=context,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
            live_projection_document=live_projection_document,
            live_projection_frame=live_projection_frame,
        )
        self._publication = publication
        return invalidation

    def geometry_inputs_match(
        self,
        *,
        layout_width: float,
        font: QFont,
    ) -> bool:
        """Return whether active frames match current geometry inputs."""

        publication = self._publication
        if publication.preview_state is None:
            return True
        preview_frame = publication.preview_frame
        preview_matches = preview_frame is not None and _frame_geometry_inputs_match(
            preview_frame,
            layout_width=layout_width,
            font=font,
        )
        base_drag_frame = publication.base_drag_frame
        return preview_matches and (
            (
                publication.preview_state.base_drag_snapshot is None
                and base_drag_frame is None
            )
            or (
                base_drag_frame is not None
                and _frame_geometry_inputs_match(
                    base_drag_frame,
                    layout_width=layout_width,
                    font=font,
                )
            )
        )

    def rebuild_geometry_inputs(
        self,
        *,
        source_revision: int,
        layout_width: float,
        viewport_width: int,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
        live_projection_document: PromptProjectionDocument,
        live_projection_frame: PromptProjectionPreparedFrame,
    ) -> PromptReorderPreviewProjectionInvalidation:
        """Rebuild and atomically publish frames after geometry input changes."""

        preview_state = self._publication.preview_state
        if preview_state is None:
            return PromptReorderPreviewProjectionInvalidation()
        return self.set_preview_state(
            preview_state,
            context=PromptReorderPreviewProjectionContext.from_preview_state(
                preview_state,
                source_revision=source_revision,
                layout_width=layout_width,
                viewport_width=viewport_width,
            ),
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
            live_projection_document=live_projection_document,
            live_projection_frame=live_projection_frame,
        )

    def reset_counters(self) -> None:
        """Reset per-gesture projection cache and layout counters."""

        self._metrics.reset()

    def counters(self) -> dict[str, object]:
        """Return the stable prompt-safe counter schema."""

        return self._metrics.snapshot()

    def clear_projection_cache(self, *, reason: str) -> None:
        """Invalidate target-revisit frames when an identity input changes."""

        self._frame_cache.clear(reason=reason)

    def preview_fragments(
        self,
        *,
        start: int,
        end: int,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments from the active preview frame."""

        frame = self._publication.preview_frame
        if frame is None:
            return ()
        return frame.geometry.selection.source_range_fragments(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def base_drag_fragments(
        self,
        *,
        start: int,
        end: int,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments from the stable base-drag frame."""

        frame = self._publication.base_drag_frame
        if frame is None:
            return ()
        return frame.geometry.selection.source_range_fragments(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def preview_cursor_rect(self, *, position: int, scroll_offset: float) -> QRectF:
        """Return the preview caret rect for one raw source position."""

        publication = self._publication
        if publication.preview_frame is None or publication.preview_document is None:
            return QRectF()
        return publication.preview_frame.geometry.caret.cursor_rect(
            publication.preview_document.caret_map.state_for_source_position(position),
            scroll_offset=scroll_offset,
        )

    def base_drag_cursor_rect(
        self,
        *,
        position: int,
        scroll_offset: float,
    ) -> QRectF:
        """Return the base-drag caret rect for one raw source position."""

        publication = self._publication
        if (
            publication.base_drag_frame is None
            or publication.base_drag_document is None
        ):
            return QRectF()
        return publication.base_drag_frame.geometry.caret.cursor_rect(
            publication.base_drag_document.caret_map.state_for_source_position(
                position
            ),
            scroll_offset=scroll_offset,
        )

    def _build_publication(
        self,
        *,
        preview_state: PromptReorderPreviewState | None,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
        live_projection_document: PromptProjectionDocument | None,
        live_projection_frame: PromptProjectionPreparedFrame | None,
    ) -> tuple[
        PromptReorderPreviewProjectionPublication,
        PromptReorderPreviewProjectionInvalidation,
    ]:
        """Prepare one complete publication without exposing partial state."""

        total_started_at = reorder_drag_started_at()
        if preview_state is None:
            self._frame_cache.clear(reason="reorder_preview_clear")
            log_reorder_drag_timing(
                "surface.rebuild_reorder_projection.clear",
                started_at=total_started_at,
            )
            return (
                PromptReorderPreviewProjectionPublication(),
                PromptReorderPreviewProjectionInvalidation(
                    clear_all_geometry_reason="reorder_preview_clear",
                ),
            )

        current = self._publication
        preview_cache_key = self._frame_cache.key_for(
            preview_state.preview_snapshot,
            context=context,
            layout_key=context.preview_layout_key,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        preview_cache_hit = (
            current.preview_document is not None
            and current.preview_frame is not None
            and current.preview_cache_key == preview_cache_key
        )
        preview_elapsed_ms = 0.0
        if preview_cache_hit:
            self._metrics.active_cache_hit_count += 1
            preview_document = current.preview_document
            preview_frame = current.preview_frame
            log_reorder_drag_event(
                "surface.rebuild_reorder_projection.preview_cache_hit",
                gesture_id=preview_state.instrumentation_gesture_id,
                event_id=preview_state.instrumentation_event_id,
                reason=preview_state.instrumentation_reason,
                cache_source="active",
                text_length=len(
                    preview_state.preview_snapshot.document_view.source_text
                ),
                rendered_range_count=len(
                    preview_state.preview_snapshot.chip_rendered_ranges_by_index
                ),
            )
        else:
            cached_preview = self._frame_cache.get(preview_cache_key)
            if cached_preview is not None:
                preview_document = cached_preview.document
                preview_frame = cached_preview.frame
                preview_cache_hit = True
                log_reorder_drag_event(
                    "surface.rebuild_reorder_projection.preview_cache_hit",
                    gesture_id=preview_state.instrumentation_gesture_id,
                    event_id=preview_state.instrumentation_event_id,
                    reason=preview_state.instrumentation_reason,
                    cache_source="lru",
                    text_length=cached_preview.text_length,
                    rendered_range_count=cached_preview.rendered_range_count,
                )
            else:
                phase_started_at = reorder_drag_started_at()
                reusable = self._reusable_from_publication(current)
                if reusable is None:
                    reusable = self._live_reusable(
                        document=live_projection_document,
                        frame=live_projection_frame,
                        context=context,
                        font=font,
                        palette=palette,
                        semantic_palette=semantic_palette,
                    )
                preview_document, preview_frame = self._build_frame(
                    preview_state.preview_snapshot,
                    preview_state=preview_state,
                    context=context,
                    font=font,
                    palette=palette,
                    semantic_palette=semantic_palette,
                    reusable=reusable,
                )
                self._frame_cache.store(
                    key=preview_cache_key,
                    snapshot=preview_state.preview_snapshot,
                    document=preview_document,
                    frame=preview_frame,
                )
                preview_elapsed_ms = log_reorder_drag_timing(
                    "surface.rebuild_reorder_projection.preview",
                    started_at=phase_started_at,
                    gesture_id=preview_state.instrumentation_gesture_id,
                    event_id=preview_state.instrumentation_event_id,
                    reason=preview_state.instrumentation_reason,
                    cache_hit=False,
                    **self._frame_cache.diagnostic_context(preview_cache_key),
                )

        if preview_state.base_drag_snapshot is None:
            log_reorder_drag_timing(
                "surface.rebuild_reorder_projection.total",
                started_at=total_started_at,
                gesture_id=preview_state.instrumentation_gesture_id,
                event_id=preview_state.instrumentation_event_id,
                reason=preview_state.instrumentation_reason,
                preview_cache_hit=preview_cache_hit,
                base_drag_cache_hit=False,
                has_base_drag=False,
                preview_elapsed_ms=f"{preview_elapsed_ms:.3f}",
            )
            return (
                PromptReorderPreviewProjectionPublication(
                    preview_state=preview_state,
                    preview_document=preview_document,
                    preview_frame=preview_frame,
                    preview_cache_key=preview_cache_key,
                ),
                PromptReorderPreviewProjectionInvalidation(
                    clear_base_drag_geometry_reason="base_drag_snapshot_missing",
                ),
            )

        base_drag_cache_key = self._frame_cache.key_for(
            preview_state.base_drag_snapshot,
            context=replace(context, active_drop_target_identity=None),
            layout_key=context.base_drag_layout_key,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        base_cache_hit = (
            current.base_drag_document is not None
            and current.base_drag_frame is not None
            and current.base_drag_cache_key == base_drag_cache_key
        )
        base_elapsed_ms = 0.0
        invalidation = PromptReorderPreviewProjectionInvalidation()
        if base_cache_hit:
            base_drag_document = current.base_drag_document
            base_drag_frame = current.base_drag_frame
            log_reorder_drag_event(
                "surface.rebuild_reorder_projection.base_drag_cache_hit",
                gesture_id=preview_state.instrumentation_gesture_id,
                event_id=preview_state.instrumentation_event_id,
                reason=preview_state.instrumentation_reason,
            )
        else:
            phase_started_at = reorder_drag_started_at()
            assert preview_document is not None
            assert preview_frame is not None
            reusable = PromptReorderReusablePreviewLayout(
                identity=self._frame_cache.layout_identity(preview_cache_key),
                render_plan_hash=preview_cache_key.render_plan_hash,
                document=preview_document,
                frame=preview_frame,
            )
            if self._frame_builder.can_reuse_exactly(
                reusable,
                identity=self._frame_cache.layout_identity(base_drag_cache_key),
                render_plan_hash=base_drag_cache_key.render_plan_hash,
                snapshot=preview_state.base_drag_snapshot,
            ):
                base_drag_document = preview_document
                base_drag_frame = preview_frame
                self._metrics.exact_layout_reuse_count += 1
                log_reorder_drag_event(
                    "surface.rebuild_reorder_projection.base_drag_exact_reuse",
                    gesture_id=preview_state.instrumentation_gesture_id,
                    event_id=preview_state.instrumentation_event_id,
                    reason=preview_state.instrumentation_reason,
                    **self._frame_cache.diagnostic_context(base_drag_cache_key),
                )
            else:
                base_drag_document, base_drag_frame = self._build_frame(
                    preview_state.base_drag_snapshot,
                    preview_state=preview_state,
                    context=context,
                    font=font,
                    palette=palette,
                    semantic_palette=semantic_palette,
                    reusable=reusable,
                )
            invalidation = PromptReorderPreviewProjectionInvalidation(
                clear_base_drag_geometry_reason="base_drag_projection_rebuild",
            )
            base_elapsed_ms = log_reorder_drag_timing(
                "surface.rebuild_reorder_projection.base_drag",
                started_at=phase_started_at,
                gesture_id=preview_state.instrumentation_gesture_id,
                event_id=preview_state.instrumentation_event_id,
                reason=preview_state.instrumentation_reason,
                cache_hit=False,
                **self._frame_cache.diagnostic_context(base_drag_cache_key),
            )

        log_reorder_drag_timing(
            "surface.rebuild_reorder_projection.total",
            started_at=total_started_at,
            gesture_id=preview_state.instrumentation_gesture_id,
            event_id=preview_state.instrumentation_event_id,
            reason=preview_state.instrumentation_reason,
            preview_cache_hit=preview_cache_hit,
            base_drag_cache_hit=base_cache_hit,
            has_base_drag=True,
            preview_elapsed_ms=f"{preview_elapsed_ms:.3f}",
            base_elapsed_ms=f"{base_elapsed_ms:.3f}",
        )
        return (
            PromptReorderPreviewProjectionPublication(
                preview_state=preview_state,
                preview_document=preview_document,
                preview_frame=preview_frame,
                preview_cache_key=preview_cache_key,
                base_drag_document=base_drag_document,
                base_drag_frame=base_drag_frame,
                base_drag_cache_key=base_drag_cache_key,
            ),
            invalidation,
        )

    def _build_frame(
        self,
        snapshot: PromptReorderProjectionSnapshot,
        *,
        preview_state: PromptReorderPreviewState,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
        reusable: PromptReorderReusablePreviewLayout | None,
    ) -> tuple[PromptProjectionDocument, PromptProjectionPreparedFrame]:
        """Build one frame through the sole prepared-frame construction owner."""

        return self._frame_builder.build(
            snapshot,
            identity=self._frame_cache.layout_identity_for_inputs(
                context=context,
                font=font,
                palette=palette,
                semantic_palette=semantic_palette,
            ),
            layout_width=context.layout_width,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
            gesture_id=preview_state.instrumentation_gesture_id,
            event_id=preview_state.instrumentation_event_id,
            reason=preview_state.instrumentation_reason,
            reusable=reusable,
        )

    def _reusable_from_publication(
        self,
        publication: PromptReorderPreviewProjectionPublication,
    ) -> PromptReorderReusablePreviewLayout | None:
        """Return the active frame with its stable reuse identity."""

        if (
            publication.preview_document is None
            or publication.preview_frame is None
            or publication.preview_cache_key is None
        ):
            return None
        return PromptReorderReusablePreviewLayout(
            identity=self._frame_cache.layout_identity(publication.preview_cache_key),
            render_plan_hash=publication.preview_cache_key.render_plan_hash,
            document=publication.preview_document,
            frame=publication.preview_frame,
        )

    def _live_reusable(
        self,
        *,
        document: PromptProjectionDocument | None,
        frame: PromptProjectionPreparedFrame | None,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderReusablePreviewLayout | None:
        """Return a live-frame seed eligible only for copy-on-write reflow."""

        if document is None or frame is None:
            return None
        return PromptReorderReusablePreviewLayout(
            identity=self._frame_cache.layout_identity_for_inputs(
                context=context,
                font=font,
                palette=palette,
                semantic_palette=semantic_palette,
            ),
            render_plan_hash="live-layout-seed-not-exact-reuse",
            document=document,
            frame=frame,
        )


def _frame_geometry_inputs_match(
    frame: PromptProjectionPreparedFrame,
    *,
    layout_width: float,
    font: QFont,
) -> bool:
    """Return whether one frame matches current geometry-affecting inputs."""

    configuration = frame.output.configuration
    return (
        configuration.base_font == font
        and abs(configuration.text_width - layout_width) < 0.01
    )


__all__ = ["PromptReorderPreviewProjectionOwner"]
