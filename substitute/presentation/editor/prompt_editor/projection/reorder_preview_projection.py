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

"""Own projection layouts used by prompt segment reorder previews."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass, replace

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
    PromptSyntaxProfile,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)

from .applicator import PromptProjectionApplicator
from .layout_engine import PromptProjectionLayout
from .model import PromptProjectionDisplayMode, PromptProjectionDocument
from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_preview import (
    PromptReorderPreviewState,
    PromptReorderProjectionSnapshot,
)
from .session import PromptProjectionSession
from .tokens import (
    PromptEmphasisPrefixRenderer,
    PromptEmphasisSuffixRenderer,
    PromptLoraInlineObjectRenderer,
    PromptProjectionInlineObjectRendererRegistry,
    PromptWildcardInlineObjectRenderer,
)

_SLOW_REORDER_PROJECTION_LAYOUT_MS = 8.0
_REORDER_PREVIEW_PROJECTION_CACHE_LIMIT = 16
_REORDER_PROJECTION_SNAPSHOT_CACHE_LIMIT = 64
_SLOW_RENDER_PLAN_MS = 8.0


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshotBuildCacheKey:
    """Identify one display-only reorder preview snapshot build result.

    The projection preview module owns this key because the cached value feeds
    only display projection and overlay geometry refresh. It deliberately
    includes layout and active-target identity so revisiting a target can reuse
    prepared syntax work without allowing a different target's display snapshot
    to leak into the current preview.
    """

    cache_namespace: str
    syntax_profile_identity: int
    source_revision: int
    viewport_width: int
    scroll_position: int
    layout_key: Hashable | None
    active_drop_target_identity: Hashable | None
    preview_text: str
    chip_rendered_ranges: tuple[tuple[int, tuple[int, int]], ...]
    chip_owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, tuple[int, int]], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionResult:
    """Carry overlay and projection snapshots built for one reorder layout."""

    preview_snapshot: PromptReorderPreviewSnapshot
    projection_snapshot: PromptReorderProjectionSnapshot


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionContext:
    """Identify viewport and target inputs for one reorder projection preview.

    The projection service owns display-only preview state. It uses this context
    to reject stale projection documents and layouts without depending on a
    QWidget, overlay gesture owner, or commit snapshot owner.
    """

    source_revision: int
    layout_width: float
    viewport_width: int
    scroll_offset: int
    preview_layout_key: Hashable | None = None
    base_drag_layout_key: Hashable | None = None
    active_drop_target_identity: Hashable | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionInvalidation:
    """Describe geometry caches that surface must clear after projection updates."""

    clear_all_geometry_reason: str | None = None
    clear_base_drag_geometry_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshotCacheKey:
    """Identify one cached reorder projection document and layout."""

    source_revision: int
    viewport_width: int
    scroll_offset: int
    layout_width_x100: int
    layout_key: Hashable | None
    active_drop_target_identity: Hashable | None
    render_plan_hash: str
    font_key: str
    palette_cache_key: int
    semantic_palette_hash: str
    snapshot_hash: str
    text_length: int
    rendered_ranges: tuple[tuple[int, tuple[int, int]], ...]
    owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, tuple[int, int]], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionLayoutCacheEntry:
    """Store one reorder-preview projection document/layout for target revisits."""

    document: PromptProjectionDocument
    layout: PromptProjectionLayout
    text_length: int
    rendered_range_count: int


class PromptReorderPreviewProjectionProvider:
    """Build display-only reorder preview snapshots behind an explicit cache.

    Interaction owners call this projection-layer service to prepare display
    preview state for the surface and overlay. The prepared result is not a
    commit snapshot and must not be used to decide whether Alt release mutates
    source text.
    """

    def __init__(
        self,
        *,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> None:
        """Store services required for projection snapshot construction."""

        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._cache: dict[
            PromptReorderProjectionSnapshotBuildCacheKey,
            PromptReorderProjectionSnapshot,
        ] = {}
        self._cache_order: list[PromptReorderProjectionSnapshotBuildCacheKey] = []

    def build_projection_snapshot(
        self,
        *,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView | None,
        reorder_state: PromptReorderStateView | None = None,
        cache_namespace: str,
        source_revision: int,
        viewport_width: int,
        scroll_position: int,
        layout_key: Hashable | None,
        active_drop_target_identity: Hashable | None,
        gesture_id: int | None,
        event_id: int | None,
        reason: str | None,
        record_render_plan_elapsed: Callable[[float], object] | None = None,
    ) -> PromptReorderPreviewProjectionResult | None:
        """Return projection-ready preview state for one reorder layout view."""

        if layout_view is None:
            return None

        total_started_at = reorder_drag_started_at()
        phase_started_at = reorder_drag_started_at()
        preview_snapshot = (
            self._document_service.build_reorder_preview_snapshot(
                document_view,
                layout_view,
            )
            if reorder_state is None
            else self._document_service.build_reorder_preview_snapshot_from_state(
                document_view,
                reorder_state,
                layout_view=layout_view,
            )
        )
        snapshot_elapsed_ms = log_reorder_drag_timing(
            "projection.reorder_preview.document_snapshot",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
            text_length=len(preview_snapshot.text),
            rendered_range_count=len(preview_snapshot.chip_rendered_ranges_by_index),
            gap_range_count=len(preview_snapshot.gap_ranges_by_index),
        )
        cache_key = self._cache_key(
            preview_snapshot,
            cache_namespace=cache_namespace,
            source_revision=source_revision,
            viewport_width=viewport_width,
            scroll_position=scroll_position,
            layout_key=layout_key,
            active_drop_target_identity=active_drop_target_identity,
        )
        cached_snapshot = self._cache.get(cache_key)
        if cached_snapshot is not None:
            self._touch_cache_key(cache_key)
            log_reorder_drag_event(
                "projection.reorder_preview.cache.hit",
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                namespace=cache_namespace,
                text_length=len(preview_snapshot.text),
                row_count=len(layout_view.rows),
                gap_count=len(layout_view.gaps),
                rendered_range_count=len(
                    preview_snapshot.chip_rendered_ranges_by_index
                ),
                cache_size=len(self._cache),
            )
            log_reorder_drag_timing(
                "projection.reorder_preview.build_total",
                started_at=total_started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                reason=reason,
                namespace=cache_namespace,
                cache_hit=True,
                row_count=len(layout_view.rows),
                gap_count=len(layout_view.gaps),
                text_length=len(preview_snapshot.text),
                segment_count=len(cached_snapshot.document_view.segments),
                snapshot_elapsed_ms=f"{snapshot_elapsed_ms:.3f}",
                document_view_elapsed_ms="0.000",
                render_plan_elapsed_ms="0.000",
            )
            return PromptReorderPreviewProjectionResult(
                preview_snapshot=preview_snapshot,
                projection_snapshot=cached_snapshot,
            )

        log_reorder_drag_event(
            "projection.reorder_preview.cache.miss",
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            namespace=cache_namespace,
            text_length=len(preview_snapshot.text),
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
            rendered_range_count=len(preview_snapshot.chip_rendered_ranges_by_index),
            cache_size=len(self._cache),
        )
        phase_started_at = reorder_drag_started_at()
        preview_document_view = self._document_service.build_document_view(
            preview_snapshot.text
        )
        document_view_elapsed_ms = log_reorder_drag_timing(
            "projection.reorder_preview.document_view",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            text_length=len(preview_snapshot.text),
            segment_count=len(preview_document_view.segments),
        )
        phase_started_at = reorder_drag_started_at()
        preview_render_plan = self._syntax_service.build_render_plan(
            preview_document_view,
            self._syntax_profile,
        )
        render_plan_elapsed_ms = log_reorder_drag_timing(
            "projection.reorder_preview.render_plan",
            started_at=phase_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            text_length=len(preview_snapshot.text),
            syntax_span_count=len(preview_render_plan.syntax_spans),
            renderer_view_count=len(preview_render_plan.renderer_views),
        )
        if record_render_plan_elapsed is not None:
            record_render_plan_elapsed(render_plan_elapsed_ms)
        if render_plan_elapsed_ms >= _SLOW_RENDER_PLAN_MS:
            log_reorder_drag_event(
                "slow.render_plan",
                gesture_id=gesture_id,
                event_id=event_id,
                elapsed_ms=f"{render_plan_elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_RENDER_PLAN_MS:.3f}",
                namespace=cache_namespace,
                reason=reason,
                text_length=len(preview_snapshot.text),
                syntax_span_count=len(preview_render_plan.syntax_spans),
                renderer_view_count=len(preview_render_plan.renderer_views),
            )
        projection_snapshot = PromptReorderProjectionSnapshot(
            document_view=preview_document_view,
            render_plan=preview_render_plan,
            chip_rendered_ranges_by_index=preview_snapshot.chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=preview_snapshot.chip_owned_ranges_by_index,
            gap_ranges_by_index=preview_snapshot.gap_ranges_by_index,
        )
        self._store_cache_entry(cache_key, projection_snapshot)
        log_reorder_drag_timing(
            "projection.reorder_preview.build_total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            reason=reason,
            namespace=cache_namespace,
            cache_hit=False,
            row_count=len(layout_view.rows),
            gap_count=len(layout_view.gaps),
            text_length=len(preview_snapshot.text),
            segment_count=len(preview_document_view.segments),
            snapshot_elapsed_ms=f"{snapshot_elapsed_ms:.3f}",
            document_view_elapsed_ms=f"{document_view_elapsed_ms:.3f}",
            render_plan_elapsed_ms=f"{render_plan_elapsed_ms:.3f}",
        )
        return PromptReorderPreviewProjectionResult(
            preview_snapshot=preview_snapshot,
            projection_snapshot=projection_snapshot,
        )

    def clear_cache(self, *, reason: str) -> None:
        """Clear cached reorder projection snapshots when their inputs may change."""

        if not self._cache:
            return
        log_reorder_drag_event(
            "projection.reorder_preview.cache.invalidate",
            reason=reason,
            cache_size=len(self._cache),
        )
        self._cache.clear()
        self._cache_order.clear()

    def _cache_key(
        self,
        snapshot: PromptReorderPreviewSnapshot,
        *,
        cache_namespace: str,
        source_revision: int,
        viewport_width: int,
        scroll_position: int,
        layout_key: Hashable | None,
        active_drop_target_identity: Hashable | None,
    ) -> PromptReorderProjectionSnapshotBuildCacheKey:
        """Return the content identity for one cached reorder projection snapshot."""

        return PromptReorderProjectionSnapshotBuildCacheKey(
            cache_namespace=cache_namespace,
            syntax_profile_identity=id(self._syntax_profile),
            source_revision=source_revision,
            viewport_width=viewport_width,
            scroll_position=scroll_position,
            layout_key=layout_key,
            active_drop_target_identity=active_drop_target_identity,
            preview_text=snapshot.text,
            chip_rendered_ranges=tuple(
                sorted(snapshot.chip_rendered_ranges_by_index.items())
            ),
            chip_owned_ranges=tuple(
                sorted(
                    (
                        segment_index,
                        tuple(ranges),
                    )
                    for segment_index, ranges in snapshot.chip_owned_ranges_by_index.items()
                )
            ),
            gap_ranges=tuple(sorted(snapshot.gap_ranges_by_index.items())),
        )

    def _store_cache_entry(
        self,
        cache_key: PromptReorderProjectionSnapshotBuildCacheKey,
        snapshot: PromptReorderProjectionSnapshot,
    ) -> None:
        """Store one projection snapshot while keeping the reorder cache bounded."""

        self._cache[cache_key] = snapshot
        self._touch_cache_key(cache_key)
        while len(self._cache_order) > _REORDER_PROJECTION_SNAPSHOT_CACHE_LIMIT:
            oldest_key = self._cache_order.pop(0)
            self._cache.pop(oldest_key, None)

    def _touch_cache_key(
        self,
        cache_key: PromptReorderProjectionSnapshotBuildCacheKey,
    ) -> None:
        """Move a cache key to the most-recent position."""

        try:
            self._cache_order.remove(cache_key)
        except ValueError:
            pass
        self._cache_order.append(cache_key)


class PromptReorderPreviewProjectionService:
    """Own display-only reorder preview projection documents, layouts, and cache."""

    def __init__(
        self,
        *,
        projection_applicator: PromptProjectionApplicator,
        thumbnail_cache: PromptLoraThumbnailCache,
        cache_limit: int = _REORDER_PREVIEW_PROJECTION_CACHE_LIMIT,
    ) -> None:
        """Store projection collaborators without taking QWidget ownership."""

        self._projection_applicator = projection_applicator
        self._thumbnail_cache = thumbnail_cache
        self._cache_limit = cache_limit
        self._preview_session = PromptProjectionSession()
        self._preview_state: PromptReorderPreviewState | None = None
        self._preview_document: PromptProjectionDocument | None = None
        self._preview_layout: PromptProjectionLayout | None = None
        self._preview_cache_key: PromptReorderProjectionSnapshotCacheKey | None = None
        self._base_drag_document: PromptProjectionDocument | None = None
        self._base_drag_layout: PromptProjectionLayout | None = None
        self._base_drag_cache_key: PromptReorderProjectionSnapshotCacheKey | None = None
        self._preview_projection_cache: OrderedDict[
            PromptReorderProjectionSnapshotCacheKey,
            PromptReorderProjectionLayoutCacheEntry,
        ] = OrderedDict()
        self.reset_counters()

    @property
    def preview_state(self) -> PromptReorderPreviewState | None:
        """Return the active display-only reorder preview state."""

        return self._preview_state

    @property
    def preview_document(self) -> PromptProjectionDocument | None:
        """Return the active preview projection document."""

        return self._preview_document

    @property
    def preview_layout(self) -> PromptProjectionLayout | None:
        """Return the active preview projection layout."""

        return self._preview_layout

    @property
    def base_drag_document(self) -> PromptProjectionDocument | None:
        """Return the stable base-drag projection document."""

        return self._base_drag_document

    @property
    def base_drag_layout(self) -> PromptProjectionLayout | None:
        """Return the stable base-drag projection layout."""

        return self._base_drag_layout

    def is_active(self) -> bool:
        """Return whether reorder preview projection currently suppresses live paint."""

        return self._preview_layout is not None

    def set_preview_state(
        self,
        preview_state: PromptReorderPreviewState | None,
        *,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderPreviewProjectionInvalidation:
        """Replace active preview state and rebuild or reuse projection layouts."""

        self._preview_state = preview_state
        return self._rebuild_preview_projection(
            context=context,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )

    def reset_counters(self) -> None:
        """Reset per-gesture reorder projection cache counters."""

        self._projection_snapshot_rebuild_count = 0
        self._preview_projection_active_cache_hit_count = 0
        self._preview_projection_lru_cache_hit_count = 0
        self._preview_projection_cache_miss_count = 0

    def counters(self) -> dict[str, object]:
        """Return prompt-safe reorder projection cache counters."""

        return {
            "projection_snapshot_rebuild_count": (
                self._projection_snapshot_rebuild_count
            ),
            "preview_projection_active_cache_hit_count": (
                self._preview_projection_active_cache_hit_count
            ),
            "preview_projection_lru_cache_hit_count": (
                self._preview_projection_lru_cache_hit_count
            ),
            "preview_projection_cache_miss_count": (
                self._preview_projection_cache_miss_count
            ),
        }

    def clear_projection_cache(self, *, reason: str) -> None:
        """Invalidate cached reorder-preview projection document/layout entries."""

        cache_size = len(self._preview_projection_cache)
        self._preview_projection_cache.clear()
        if cache_size:
            log_reorder_drag_event(
                "cache.preview_projection.invalidate",
                reason=reason,
                cache_size=cache_size,
            )

    def preview_fragments(
        self,
        *,
        start: int,
        end: int,
        viewport_rect: QRectF,
        scroll_offset: float,
    ) -> tuple[QRectF, ...]:
        """Return wrapped fragments from the active preview projection layout."""

        if self._preview_layout is None:
            return ()
        return self._preview_layout.source_range_fragments(
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
        """Return wrapped fragments from the stable base-drag projection layout."""

        if self._base_drag_layout is None:
            return ()
        return self._base_drag_layout.source_range_fragments(
            start,
            end,
            viewport_rect=viewport_rect,
            scroll_offset=scroll_offset,
        )

    def preview_cursor_rect(self, *, position: int, scroll_offset: float) -> QRectF:
        """Return the preview caret rect for one raw preview source position."""

        if self._preview_layout is None or self._preview_document is None:
            return QRectF()
        return self._preview_layout.cursor_rect(
            self._preview_document.caret_map.state_for_source_position(position),
            scroll_offset=scroll_offset,
        )

    def base_drag_cursor_rect(self, *, position: int, scroll_offset: float) -> QRectF:
        """Return the stable base-drag caret rect for one raw source position."""

        if self._base_drag_layout is None or self._base_drag_document is None:
            return QRectF()
        return self._base_drag_layout.cursor_rect(
            self._base_drag_document.caret_map.state_for_source_position(position),
            scroll_offset=scroll_offset,
        )

    def _rebuild_preview_projection(
        self,
        *,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderPreviewProjectionInvalidation:
        """Rebuild the explicit reorder preview projection state when active."""

        total_started_at = reorder_drag_started_at()
        preview_state = self._preview_state
        if preview_state is None:
            self._preview_document = None
            self._preview_layout = None
            self._preview_cache_key = None
            self._base_drag_document = None
            self._base_drag_layout = None
            self._base_drag_cache_key = None
            self.clear_projection_cache(reason="reorder_preview_clear")
            log_reorder_drag_timing(
                "surface.rebuild_reorder_projection.clear",
                started_at=total_started_at,
            )
            return PromptReorderPreviewProjectionInvalidation(
                clear_all_geometry_reason="reorder_preview_clear",
            )

        preview_cache_key = self._projection_snapshot_cache_key(
            preview_state.preview_snapshot,
            context=context,
            layout_key=context.preview_layout_key,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        preview_cache_hit = self._has_active_preview_projection_cache(preview_cache_key)
        preview_elapsed_ms = 0.0
        if preview_cache_hit:
            self._preview_projection_active_cache_hit_count += 1
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
            cached_preview = self._preview_projection_cache_entry(preview_cache_key)
            if cached_preview is not None:
                self._preview_document = cached_preview.document
                self._preview_layout = cached_preview.layout
                self._preview_cache_key = preview_cache_key
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
                preview_document, preview_layout = self._build_projection_snapshot(
                    preview_state.preview_snapshot,
                    context=context,
                    font=font,
                    palette=palette,
                    semantic_palette=semantic_palette,
                )
                self._preview_document = preview_document
                self._preview_layout = preview_layout
                self._preview_cache_key = preview_cache_key
                self._store_preview_projection_cache_entry(
                    key=preview_cache_key,
                    snapshot=preview_state.preview_snapshot,
                    document=preview_document,
                    layout=preview_layout,
                )
                preview_elapsed_ms = log_reorder_drag_timing(
                    "surface.rebuild_reorder_projection.preview",
                    started_at=phase_started_at,
                    gesture_id=preview_state.instrumentation_gesture_id,
                    event_id=preview_state.instrumentation_event_id,
                    reason=preview_state.instrumentation_reason,
                    cache_hit=False,
                    **self._cache_context(preview_cache_key),
                )

        if preview_state.base_drag_snapshot is None:
            self._base_drag_document = None
            self._base_drag_layout = None
            self._base_drag_cache_key = None
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
            return PromptReorderPreviewProjectionInvalidation(
                clear_base_drag_geometry_reason="base_drag_snapshot_missing",
            )

        base_drag_cache_key = self._projection_snapshot_cache_key(
            preview_state.base_drag_snapshot,
            context=replace(context, active_drop_target_identity=None),
            layout_key=context.base_drag_layout_key,
            font=font,
            palette=palette,
            semantic_palette=semantic_palette,
        )
        base_cache_hit = self._has_active_base_drag_projection_cache(
            base_drag_cache_key
        )
        base_elapsed_ms = 0.0
        invalidation = PromptReorderPreviewProjectionInvalidation()
        if not base_cache_hit:
            phase_started_at = reorder_drag_started_at()
            self._base_drag_document, self._base_drag_layout = (
                self._build_projection_snapshot(
                    preview_state.base_drag_snapshot,
                    context=context,
                    font=font,
                    palette=palette,
                    semantic_palette=semantic_palette,
                )
            )
            self._base_drag_cache_key = base_drag_cache_key
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
                **self._cache_context(base_drag_cache_key),
            )
        else:
            log_reorder_drag_event(
                "surface.rebuild_reorder_projection.base_drag_cache_hit",
                gesture_id=preview_state.instrumentation_gesture_id,
                event_id=preview_state.instrumentation_event_id,
                reason=preview_state.instrumentation_reason,
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
        return invalidation

    def _build_projection_snapshot(
        self,
        snapshot: PromptReorderProjectionSnapshot,
        *,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> tuple[PromptProjectionDocument, PromptProjectionLayout]:
        """Build one projection document and layout from a reorder snapshot."""

        preview_state = self._preview_state
        self._projection_snapshot_rebuild_count += 1
        total_started_at = reorder_drag_started_at()
        phase_started_at = reorder_drag_started_at()
        projection_document = self._projection_applicator.build_projection(
            snapshot.document_view,
            snapshot.render_plan,
            display_mode=PromptProjectionDisplayMode.PROJECTED,
            session=self._preview_session,
            active_span_range=None,
            decoration_accent_ranges=(),
            scene_error_keys=frozenset(),
        )
        build_projection_elapsed_ms = log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.build_projection",
            started_at=phase_started_at,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            syntax_span_count=len(snapshot.render_plan.syntax_spans),
            run_count=len(projection_document.runs),
            token_count=len(projection_document.tokens),
            layout_width=f"{context.layout_width:.2f}",
        )
        phase_started_at = reorder_drag_started_at()
        projection_layout = PromptProjectionLayout(
            PromptProjectionInlineObjectRendererRegistry(
                (
                    PromptEmphasisPrefixRenderer(),
                    PromptEmphasisSuffixRenderer(),
                    PromptLoraInlineObjectRenderer(
                        self._thumbnail_cache,
                        suppress_banners=True,
                    ),
                    PromptWildcardInlineObjectRenderer(),
                )
            )
        )
        projection_layout.set_base_font(font)
        projection_layout.set_palette(palette)
        projection_layout.set_semantic_palette(semantic_palette)
        projection_layout.set_projection_and_text_width(
            projection_document,
            context.layout_width,
            prompt_document_view=snapshot.document_view,
        )
        layout_elapsed_ms = log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.layout",
            started_at=phase_started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            run_count=len(projection_document.runs),
            token_count=len(projection_document.tokens),
            visual_line_count=projection_layout.line_count(),
            text_fragment_count=projection_layout.text_fragment_count(),
            inline_object_count=projection_layout.inline_object_fragment_count(),
            chip_count=len(snapshot.chip_rendered_ranges_by_index),
            layout_width=f"{context.layout_width:.2f}",
            content_width=f"{projection_layout.content_size().width():.2f}",
            content_height=f"{projection_layout.content_size().height():.2f}",
        )
        if layout_elapsed_ms >= _SLOW_REORDER_PROJECTION_LAYOUT_MS:
            log_reorder_drag_event(
                "slow.projection_layout",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reason=""
                if preview_state is None
                else preview_state.instrumentation_reason,
                elapsed_ms=f"{layout_elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                text_length=len(snapshot.document_view.source_text),
                segment_count=len(snapshot.document_view.segments),
                run_count=len(projection_document.runs),
                token_count=len(projection_document.tokens),
                visual_line_count=projection_layout.line_count(),
                text_fragment_count=projection_layout.text_fragment_count(),
                inline_object_count=projection_layout.inline_object_fragment_count(),
                chip_count=len(snapshot.chip_rendered_ranges_by_index),
                layout_width=f"{context.layout_width:.2f}",
            )
            log_reorder_drag_event(
                "budget.projection_layout_exceeded",
                gesture_id=None
                if preview_state is None
                else preview_state.instrumentation_gesture_id,
                event_id=None
                if preview_state is None
                else preview_state.instrumentation_event_id,
                reason=""
                if preview_state is None
                else preview_state.instrumentation_reason,
                elapsed_ms=f"{layout_elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_REORDER_PROJECTION_LAYOUT_MS:.3f}",
                text_length=len(snapshot.document_view.source_text),
                segment_count=len(snapshot.document_view.segments),
                visual_line_count=projection_layout.line_count(),
                layout_width=f"{context.layout_width:.2f}",
            )
        log_reorder_drag_timing(
            "surface.build_reorder_projection_snapshot.total",
            started_at=total_started_at,
            gesture_id=None
            if preview_state is None
            else preview_state.instrumentation_gesture_id,
            event_id=None
            if preview_state is None
            else preview_state.instrumentation_event_id,
            reason=""
            if preview_state is None
            else preview_state.instrumentation_reason,
            text_length=len(snapshot.document_view.source_text),
            segment_count=len(snapshot.document_view.segments),
            rendered_range_count=len(snapshot.chip_rendered_ranges_by_index),
            gap_range_count=len(snapshot.gap_ranges_by_index),
            layout_width=f"{context.layout_width:.2f}",
            build_projection_elapsed_ms=f"{build_projection_elapsed_ms:.3f}",
            layout_elapsed_ms=f"{layout_elapsed_ms:.3f}",
        )
        return projection_document, projection_layout

    def _preview_projection_cache_entry(
        self,
        key: PromptReorderProjectionSnapshotCacheKey,
    ) -> PromptReorderProjectionLayoutCacheEntry | None:
        """Return and refresh one cached reorder-preview projection entry."""

        entry = self._preview_projection_cache.get(key)
        if entry is None:
            self._preview_projection_cache_miss_count += 1
            log_reorder_drag_event(
                "cache.preview_projection.miss",
                cache_size=len(self._preview_projection_cache),
                **self._cache_context(key),
            )
            return None
        self._preview_projection_cache.move_to_end(key)
        self._preview_projection_lru_cache_hit_count += 1
        log_reorder_drag_event(
            "cache.preview_projection.hit",
            cache_size=len(self._preview_projection_cache),
            text_length=entry.text_length,
            rendered_range_count=entry.rendered_range_count,
            **self._cache_context(key),
        )
        return entry

    def _store_preview_projection_cache_entry(
        self,
        *,
        key: PromptReorderProjectionSnapshotCacheKey,
        snapshot: PromptReorderProjectionSnapshot,
        document: PromptProjectionDocument,
        layout: PromptProjectionLayout,
    ) -> None:
        """Store one reorder-preview projection entry and evict oldest entries."""

        self._preview_projection_cache[key] = PromptReorderProjectionLayoutCacheEntry(
            document=document,
            layout=layout,
            text_length=len(snapshot.document_view.source_text),
            rendered_range_count=len(snapshot.chip_rendered_ranges_by_index),
        )
        self._preview_projection_cache.move_to_end(key)
        while len(self._preview_projection_cache) > self._cache_limit:
            _old_key, old_entry = self._preview_projection_cache.popitem(last=False)
            log_reorder_drag_event(
                "cache.preview_projection.evict",
                cache_size=len(self._preview_projection_cache),
                text_length=old_entry.text_length,
                rendered_range_count=old_entry.rendered_range_count,
            )

    def _projection_snapshot_cache_key(
        self,
        snapshot: PromptReorderProjectionSnapshot,
        *,
        context: PromptReorderPreviewProjectionContext,
        layout_key: Hashable | None,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderProjectionSnapshotCacheKey:
        """Return the cache identity for stable reorder projection geometry."""

        snapshot_hash = _snapshot_hash(snapshot)
        return PromptReorderProjectionSnapshotCacheKey(
            source_revision=context.source_revision,
            viewport_width=context.viewport_width,
            scroll_offset=context.scroll_offset,
            layout_width_x100=int(round(context.layout_width * 100.0)),
            layout_key=layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
            render_plan_hash=_render_plan_hash(snapshot),
            font_key=font.toString(),
            palette_cache_key=int(palette.cacheKey()),
            semantic_palette_hash=_safe_key_hash(semantic_palette),
            snapshot_hash=snapshot_hash,
            text_length=len(snapshot.document_view.source_text),
            rendered_ranges=tuple(
                sorted(snapshot.chip_rendered_ranges_by_index.items())
            ),
            owned_ranges=tuple(sorted(snapshot.chip_owned_ranges_by_index.items())),
            gap_ranges=tuple(sorted(snapshot.gap_ranges_by_index.items())),
        )

    def _has_active_preview_projection_cache(
        self,
        cache_key: PromptReorderProjectionSnapshotCacheKey,
    ) -> bool:
        """Return whether the current preview document/layout match the key."""

        return (
            self._preview_document is not None
            and self._preview_layout is not None
            and self._preview_cache_key == cache_key
        )

    def _has_active_base_drag_projection_cache(
        self,
        cache_key: PromptReorderProjectionSnapshotCacheKey,
    ) -> bool:
        """Return whether the current base-drag document/layout match the key."""

        return (
            self._base_drag_document is not None
            and self._base_drag_layout is not None
            and self._base_drag_cache_key == cache_key
        )

    def _cache_context(
        self,
        key: PromptReorderProjectionSnapshotCacheKey,
    ) -> dict[str, object]:
        """Return prompt-safe diagnostics for one projection cache key."""

        return {
            "projection_cache_text_length": key.text_length,
            "projection_cache_snapshot_hash": key.snapshot_hash,
            "projection_cache_rendered_range_count": len(key.rendered_ranges),
            "projection_cache_owned_range_count": len(key.owned_ranges),
            "projection_cache_gap_range_count": len(key.gap_ranges),
            "source_revision": key.source_revision,
            "projection_cache_viewport_width": key.viewport_width,
            "projection_cache_scroll_offset": key.scroll_offset,
            "projection_cache_layout_width_x100": key.layout_width_x100,
            "projection_cache_layout_hash": _safe_key_hash(key.layout_key),
            "projection_cache_target_hash": _safe_key_hash(
                key.active_drop_target_identity
            ),
            "projection_cache_render_plan_hash": key.render_plan_hash,
            "projection_cache_font_hash": _safe_key_hash(key.font_key),
            "projection_cache_palette_key": key.palette_cache_key,
            "projection_cache_semantic_palette_hash": key.semantic_palette_hash,
        }


def _snapshot_hash(snapshot: PromptReorderProjectionSnapshot) -> str:
    """Return a prompt-safe identity for one projection snapshot."""

    digest = hashlib.sha256()
    digest.update(snapshot.document_view.source_text.encode("utf-8"))
    digest.update(repr(sorted(snapshot.chip_rendered_ranges_by_index.items())).encode())
    digest.update(repr(sorted(snapshot.chip_owned_ranges_by_index.items())).encode())
    digest.update(repr(sorted(snapshot.gap_ranges_by_index.items())).encode())
    return digest.hexdigest()[:16]


def _render_plan_hash(snapshot: PromptReorderProjectionSnapshot) -> str:
    """Return a prompt-safe identity for renderer-visible syntax inputs."""

    return hashlib.sha256(repr(snapshot.render_plan).encode("utf-8")).hexdigest()[:16]


def _safe_key_hash(key: object) -> str:
    """Return a compact diagnostic hash without logging prompt text."""

    if key is None:
        return "none"
    return hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]


__all__ = [
    "PromptReorderPreviewProjectionProvider",
    "PromptReorderPreviewProjectionResult",
    "PromptReorderPreviewProjectionContext",
    "PromptReorderPreviewProjectionInvalidation",
    "PromptReorderPreviewProjectionService",
    "PromptReorderProjectionSnapshotBuildCacheKey",
    "PromptReorderProjectionSnapshotCacheKey",
]
