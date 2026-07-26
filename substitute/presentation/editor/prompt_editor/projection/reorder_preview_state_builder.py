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

"""Build one atomic reorder preview publication from immutable adapter facts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.document.views import PromptDocumentView
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderGapPlacement,
    PromptReorderLayoutView,
    PromptReorderPreviewSnapshot,
    PromptReorderStateView,
)

from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_interaction_geometry_identity import (
    reorder_layout_view_key as layout_view_key,
)
from .reorder_preview import PromptReorderPreviewState, reorder_drop_target_identity
from .reorder_projection_snapshot_provider import (
    PromptReorderPreviewProjectionProvider,
    PromptReorderPreviewProjectionResult,
)


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewBuildRequest:
    """Carry one coherent set of facts for preview projection construction."""

    document_view: PromptDocumentView
    preview_layout_view: PromptReorderLayoutView | None
    base_drag_layout_view: PromptReorderLayoutView | None
    preview_reorder_state: PromptReorderStateView | None
    base_drag_reorder_state: PromptReorderStateView | None
    ordered_chip_indices: tuple[int, ...]
    dragged_segment_index: int | None
    drop_target: object | None
    source_revision: int
    viewport_width: int
    gesture_id: int | None
    event_id: int | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewPublication:
    """Carry the atomic surface and overlay preview values for one sync."""

    preview_state: PromptReorderPreviewState | None
    preview_snapshot: PromptReorderPreviewSnapshot | None
    base_drag_snapshot: PromptReorderPreviewSnapshot | None
    ordered_chip_indices: tuple[int, ...]


class PromptReorderPreviewStateBuilder:
    """Coordinate current, base-drag, and target preview snapshot construction."""

    def __init__(
        self,
        *,
        document_service: PromptDocumentService,
        projection_provider: PromptReorderPreviewProjectionProvider,
    ) -> None:
        """Store the lower document and semantic projection owners."""

        self._document_service = document_service
        self._projection_provider = projection_provider

    def build(
        self,
        request: PromptReorderPreviewBuildRequest,
        *,
        record_render_plan_elapsed: Callable[[float], object] | None = None,
    ) -> PromptReorderPreviewPublication:
        """Build one complete publication without mutating receiving adapters."""

        started_at = reorder_drag_started_at()
        if request.preview_layout_view is None:
            return self._build_base_drag_publication(
                request,
                started_at=started_at,
                record_render_plan_elapsed=record_render_plan_elapsed,
            )
        return self._build_active_publication(
            request,
            started_at=started_at,
            record_render_plan_elapsed=record_render_plan_elapsed,
        )

    def _build_base_drag_publication(
        self,
        request: PromptReorderPreviewBuildRequest,
        *,
        started_at: float,
        record_render_plan_elapsed: Callable[[float], object] | None,
    ) -> PromptReorderPreviewPublication:
        """Build current and base-drag snapshots before a target is active."""

        base_layout = request.base_drag_layout_view
        if base_layout is None:
            log_reorder_drag_timing(
                "interaction.sync_preview.clear",
                started_at=started_at,
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                reason=request.reason,
                ordered_count=len(request.ordered_chip_indices),
            )
            return PromptReorderPreviewPublication(
                preview_state=None,
                preview_snapshot=None,
                base_drag_snapshot=None,
                ordered_chip_indices=request.ordered_chip_indices,
            )

        current_layout = self._document_service.build_reorder_layout_view(
            request.document_view
        )
        current_result = self._build_projection(
            request,
            layout_view=current_layout,
            reorder_state=None,
            include_edge_gaps=True,
            cache_namespace="current",
            record_render_plan_elapsed=record_render_plan_elapsed,
        )
        base_result = self._build_projection(
            request,
            layout_view=base_layout,
            reorder_state=request.base_drag_reorder_state,
            include_edge_gaps=True,
            cache_namespace="base_drag",
            record_render_plan_elapsed=record_render_plan_elapsed,
        )
        publication = PromptReorderPreviewPublication(
            preview_state=PromptReorderPreviewState(
                preview_snapshot=current_result.projection_snapshot,
                base_drag_snapshot=base_result.projection_snapshot,
                ordered_chip_indices=request.ordered_chip_indices,
                dragged_chip_index=None,
                preview_layout_key=layout_view_key(current_layout),
                base_drag_layout_key=layout_view_key(base_layout),
                active_drop_target_identity=None,
                instrumentation_gesture_id=request.gesture_id,
                instrumentation_event_id=request.event_id,
                instrumentation_reason=request.reason or "",
            ),
            preview_snapshot=None,
            base_drag_snapshot=base_result.preview_snapshot,
            ordered_chip_indices=request.ordered_chip_indices,
        )
        log_reorder_drag_timing(
            "interaction.sync_preview.base_drag_only_total",
            started_at=started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=request.reason,
            ordered_count=len(request.ordered_chip_indices),
        )
        return publication

    def _build_active_publication(
        self,
        request: PromptReorderPreviewBuildRequest,
        *,
        started_at: float,
        record_render_plan_elapsed: Callable[[float], object] | None,
    ) -> PromptReorderPreviewPublication:
        """Build target preview plus an optional reusable base-drag snapshot."""

        preview_layout = request.preview_layout_view
        assert preview_layout is not None
        phase_started_at = reorder_drag_started_at()
        preview_result = self._build_projection(
            request,
            layout_view=preview_layout,
            reorder_state=request.preview_reorder_state,
            include_edge_gaps=False,
            cache_namespace="preview",
            record_render_plan_elapsed=record_render_plan_elapsed,
        )
        preview_elapsed_ms = log_reorder_drag_timing(
            "interaction.sync_preview.preview_projection_snapshot",
            started_at=phase_started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=request.reason,
            row_count=len(preview_layout.rows),
            gap_count=len(preview_layout.gaps),
            dragged_segment_index=request.dragged_segment_index,
            target_kind=reorder_drag_target_kind(request.drop_target),
        )

        phase_started_at = reorder_drag_started_at()
        base_layout = request.base_drag_layout_view
        base_result: PromptReorderPreviewProjectionResult | None
        if (
            base_layout is not None
            and base_layout == preview_layout
            and request.base_drag_reorder_state == request.preview_reorder_state
            and not any(
                gap.placement is PromptReorderGapPlacement.AFTER_LAST_ROW
                for gap in preview_layout.gaps
            )
        ):
            base_result = preview_result
            log_reorder_drag_event(
                "interaction.sync_preview.base_drag_result_exact_reuse",
                gesture_id=request.gesture_id,
                event_id=request.event_id,
                reason=request.reason,
                row_count=len(base_layout.rows),
                gap_count=len(base_layout.gaps),
            )
        else:
            base_result = (
                None
                if base_layout is None
                else self._build_projection(
                    request,
                    layout_view=base_layout,
                    reorder_state=request.base_drag_reorder_state,
                    include_edge_gaps=True,
                    cache_namespace="base_drag",
                    record_render_plan_elapsed=record_render_plan_elapsed,
                )
            )
        base_elapsed_ms = log_reorder_drag_timing(
            "interaction.sync_preview.base_drag_projection_snapshot",
            started_at=phase_started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=request.reason,
            row_count=0 if base_layout is None else len(base_layout.rows),
            gap_count=0 if base_layout is None else len(base_layout.gaps),
        )
        publication = PromptReorderPreviewPublication(
            preview_state=PromptReorderPreviewState(
                preview_snapshot=preview_result.projection_snapshot,
                base_drag_snapshot=(
                    None if base_result is None else base_result.projection_snapshot
                ),
                ordered_chip_indices=request.ordered_chip_indices,
                dragged_chip_index=request.dragged_segment_index,
                preview_layout_key=layout_view_key(preview_layout),
                base_drag_layout_key=layout_view_key(base_layout),
                active_drop_target_identity=reorder_drop_target_identity(
                    request.drop_target
                ),
                instrumentation_gesture_id=request.gesture_id,
                instrumentation_event_id=request.event_id,
                instrumentation_reason=request.reason or "",
            ),
            preview_snapshot=preview_result.preview_snapshot,
            base_drag_snapshot=(
                None if base_result is None else base_result.preview_snapshot
            ),
            ordered_chip_indices=request.ordered_chip_indices,
        )
        log_reorder_drag_timing(
            "interaction.sync_preview.total",
            started_at=started_at,
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=request.reason,
            ordered_count=len(request.ordered_chip_indices),
            dragged_segment_index=request.dragged_segment_index,
            target_kind=reorder_drag_target_kind(request.drop_target),
            preview_elapsed_ms=f"{preview_elapsed_ms:.3f}",
            base_elapsed_ms=f"{base_elapsed_ms:.3f}",
        )
        return publication

    def _build_projection(
        self,
        request: PromptReorderPreviewBuildRequest,
        *,
        layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView | None,
        include_edge_gaps: bool,
        cache_namespace: str,
        record_render_plan_elapsed: Callable[[float], object] | None,
    ) -> PromptReorderPreviewProjectionResult:
        """Build one non-null semantic snapshot from a concrete layout."""

        result = self._projection_provider.build_projection_snapshot(
            document_view=request.document_view,
            layout_view=layout_view,
            reorder_state=reorder_state,
            include_edge_gaps=include_edge_gaps,
            cache_namespace=cache_namespace,
            source_revision=request.source_revision,
            viewport_width=request.viewport_width,
            layout_key=layout_view_key(layout_view),
            gesture_id=request.gesture_id,
            event_id=request.event_id,
            reason=request.reason,
            record_render_plan_elapsed=record_render_plan_elapsed,
        )
        assert result is not None
        return result


__all__ = [
    "PromptReorderPreviewBuildRequest",
    "PromptReorderPreviewPublication",
    "PromptReorderPreviewStateBuilder",
]
