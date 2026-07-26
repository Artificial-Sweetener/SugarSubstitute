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

"""Build and cache semantic snapshots for prompt reorder projection."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.features.syntax_profile import (
    PromptSyntaxProfile,
)
from substitute.application.prompt_editor.projection.syntax_service import (
    PromptSyntaxService,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_preview import PromptReorderProjectionSnapshot

_CACHE_LIMIT = 64
_SLOW_RENDER_PLAN_MS = 8.0


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionSnapshotBuildCacheKey:
    """Identify one display-only reorder semantic snapshot."""

    syntax_profile_identity: int
    source_revision: int
    viewport_width: int
    layout_key: Hashable | None
    preview_text: str
    chip_rendered_ranges: tuple[tuple[int, tuple[int, int]], ...]
    chip_owned_ranges: tuple[tuple[int, tuple[tuple[int, int], ...]], ...]
    gap_ranges: tuple[tuple[int, tuple[int, int]], ...]


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewProjectionResult:
    """Carry source-range and semantic snapshots for one reorder layout."""

    preview_snapshot: PromptReorderPreviewSnapshot
    projection_snapshot: PromptReorderProjectionSnapshot


class PromptReorderPreviewProjectionProvider:
    """Build semantic reorder snapshots behind one bounded content cache."""

    def __init__(
        self,
        *,
        document_service: PromptDocumentService,
        syntax_service: PromptSyntaxService,
        syntax_profile: PromptSyntaxProfile,
    ) -> None:
        """Store the document and syntax authorities used for snapshot builds."""

        self._document_service = document_service
        self._syntax_service = syntax_service
        self._syntax_profile = syntax_profile
        self._cache: OrderedDict[
            PromptReorderProjectionSnapshotBuildCacheKey,
            PromptReorderProjectionSnapshot,
        ] = OrderedDict()

    def build_projection_snapshot(
        self,
        *,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView | None,
        reorder_state: PromptReorderStateView | None = None,
        include_edge_gaps: bool,
        cache_namespace: str,
        source_revision: int,
        viewport_width: int,
        layout_key: Hashable | None,
        gesture_id: int | None,
        event_id: int | None,
        reason: str | None,
        record_render_plan_elapsed: Callable[[float], object] | None = None,
    ) -> PromptReorderPreviewProjectionResult | None:
        """Return projection-ready semantic state for one reorder layout."""

        if layout_view is None:
            return None

        total_started_at = reorder_drag_started_at()
        phase_started_at = reorder_drag_started_at()
        preview_snapshot = (
            self._document_service.build_reorder_preview_snapshot(
                document_view,
                layout_view,
                include_edge_gaps=include_edge_gaps,
            )
            if reorder_state is None
            else self._document_service.build_reorder_preview_snapshot_from_state(
                document_view,
                reorder_state,
                layout_view=layout_view,
                include_edge_gaps=include_edge_gaps,
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
            source_revision=source_revision,
            viewport_width=viewport_width,
            layout_key=layout_key,
        )
        cached_snapshot = self._cache.get(cache_key)
        if cached_snapshot is not None:
            self._cache.move_to_end(cache_key)
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
        self._store(cache_key, projection_snapshot)
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
        """Clear cached semantic snapshots when their inputs may change."""

        if not self._cache:
            return
        log_reorder_drag_event(
            "projection.reorder_preview.cache.invalidate",
            reason=reason,
            cache_size=len(self._cache),
        )
        self._cache.clear()

    def _cache_key(
        self,
        snapshot: PromptReorderPreviewSnapshot,
        *,
        source_revision: int,
        viewport_width: int,
        layout_key: Hashable | None,
    ) -> PromptReorderProjectionSnapshotBuildCacheKey:
        """Return the complete content identity for a semantic snapshot."""

        return PromptReorderProjectionSnapshotBuildCacheKey(
            syntax_profile_identity=id(self._syntax_profile),
            source_revision=source_revision,
            viewport_width=viewport_width,
            layout_key=layout_key,
            preview_text=snapshot.text,
            chip_rendered_ranges=tuple(
                sorted(snapshot.chip_rendered_ranges_by_index.items())
            ),
            chip_owned_ranges=tuple(
                sorted(
                    (segment_index, tuple(ranges))
                    for segment_index, ranges in snapshot.chip_owned_ranges_by_index.items()
                )
            ),
            gap_ranges=tuple(sorted(snapshot.gap_ranges_by_index.items())),
        )

    def _store(
        self,
        key: PromptReorderProjectionSnapshotBuildCacheKey,
        snapshot: PromptReorderProjectionSnapshot,
    ) -> None:
        """Store one semantic snapshot and evict the least-recent entry."""

        self._cache[key] = snapshot
        self._cache.move_to_end(key)
        while len(self._cache) > _CACHE_LIMIT:
            self._cache.popitem(last=False)


__all__ = [
    "PromptReorderPreviewProjectionProvider",
    "PromptReorderPreviewProjectionResult",
    "PromptReorderProjectionSnapshotBuildCacheKey",
]
