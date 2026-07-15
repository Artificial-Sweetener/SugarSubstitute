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

"""Build reorder overlay visual geometry from prepared projection state."""

# mypy: disable-error-code="assignment,attr-defined,has-type,no-any-return,var-annotated"
# This mixin intentionally uses state initialized by SegmentReorderOverlay; the
# suppressions keep visual adaptation on the shell without duplicating state.

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF

from substitute.application.prompt_editor import (
    PromptReorderDropTarget,
    PromptReorderLayoutView,
)

from ..geometry import map_rect_to_host
from ..projection.observability import (
    reorder_drag_color_context,
    reorder_drag_rect_context,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometry,
    PromptReorderChipGeometrySnapshot,
    chip_geometry_context,
    chip_geometry_snapshot_context,
)
from ..projection.reorder_visual_snapshot import PromptReorderProjectionPaintSnapshot
from ..projection.reorder_geometry_cache import chip_geometry_visual_reuse_key
from ..projection.reorder_drop_targets import (
    PromptReorderDropTargetResolverInput,
    PromptReorderDropTargetVisual as _DropTargetVisual,
)
from ..projection.reorder_placement_geometry import placement_geometry_context
from ..projection.reorder_state import (
    ReorderLiveVisualGeometryKey as _LiveVisualGeometryKey,
    reorder_live_visual_geometry_key,
)
from ..reorder_drag_proxy_state import PromptReorderDragProxyRenderInputs
from .chip_visuals import PromptChipVisual
from .chip_painter import PromptChipPaintStyle
from .reorder_autoscroll import (
    PromptReorderAutoscrollContext,
    PromptReorderAutoscrollInvalidation,
)
from .reorder_displacement_intent import ReorderDisplacementIntent
from .reorder_gesture_controller import PromptReorderDragProxyPlacementContext
from .reorder_landing_shadow import (
    PromptReorderHeldShadowCaptureInput,
    PromptReorderLandingShadowRequest,
)
from .reorder_view import (
    PromptReorderViewRenderInput,
    PromptReorderViewRenderState,
    prompt_reorder_chip_widget_state,
    prompt_reorder_chip_widget_states,
    prompt_reorder_visual_for_chip_geometry,
    prompt_reorder_view_render_state,
)
from .reorder_raster_cache import ReorderRasterEntry
from .reorder_visual_cache import PromptReorderChipVisualSnapshot

if TYPE_CHECKING:
    from .reorder_overlay import _SegmentChip

_INSERTION_WIDTH = 10.0
_SHADOW_ACTUAL_MISMATCH_X = 8.0
_SHADOW_ACTUAL_MISMATCH_Y = 8.0
_SLOW_LIVE_VISUALS_MS = 8.0


@dataclass(frozen=True, slots=True)
class _VisualBuildResult:
    """Carry rebuilt reorder visuals plus cache diagnostics."""

    visuals: dict[int, PromptChipVisual]
    cache_hit_count: int
    cache_miss_count: int
    reuse_rejected_count: int


def _drop_target_kind(target: PromptReorderDropTarget | None) -> str | None:
    """Return a compact type label for drag decision context."""

    if target is None:
        return None
    return type(target).__name__


class _OverlayShellAccess:
    """Provide dynamic access to state initialized by the concrete overlay shell."""

    def __getattr__(self, name: str) -> Any:
        """Defer shell-owned attribute lookup to the concrete overlay instance."""

        raise AttributeError(name)


class PromptReorderOverlayGeometryMixin(_OverlayShellAccess):
    """Own overlay visual-state adaptation while projection owns geometry policy."""

    def _visuals_mismatch(
        self,
        expected_visual: PromptChipVisual,
        actual_visual: PromptChipVisual,
    ) -> bool:
        """Return whether two visuals disagree enough to explain a bad landing."""

        expected_rect = QRectF(expected_visual.hotspot_rect)
        actual_rect = QRectF(actual_visual.hotspot_rect)
        return (
            abs(actual_rect.center().x() - expected_rect.center().x())
            > _SHADOW_ACTUAL_MISMATCH_X
            or abs(actual_rect.center().y() - expected_rect.center().y())
            > _SHADOW_ACTUAL_MISMATCH_Y
            or abs(actual_rect.left() - expected_rect.left())
            > _SHADOW_ACTUAL_MISMATCH_X
            or abs(actual_rect.top() - expected_rect.top()) > _SHADOW_ACTUAL_MISMATCH_Y
        )

    def _chip_geometries_mismatch(
        self,
        expected_geometry: PromptReorderChipGeometry,
        actual_geometry: PromptReorderChipGeometry,
    ) -> bool:
        """Return whether two semantic chip geometries disagree after commit."""

        expected_rect = QRectF(expected_geometry.hotspot_rect)
        actual_rect = QRectF(actual_geometry.hotspot_rect)
        return (
            expected_geometry.chip_index != actual_geometry.chip_index
            or abs(actual_rect.center().x() - expected_rect.center().x())
            > _SHADOW_ACTUAL_MISMATCH_X
            or abs(actual_rect.center().y() - expected_rect.center().y())
            > _SHADOW_ACTUAL_MISMATCH_Y
            or abs(actual_rect.left() - expected_rect.left())
            > _SHADOW_ACTUAL_MISMATCH_X
            or abs(actual_rect.top() - expected_rect.top()) > _SHADOW_ACTUAL_MISMATCH_Y
        )

    def _visible_visual_for_segment(
        self,
        segment_index: int,
    ) -> PromptChipVisual | None:
        """Return the current visual used to place a segment hotspot."""

        if self._preview_mode_active():
            preview_visual = self._preview_visuals_by_index.get(segment_index)
            if preview_visual is not None:
                return preview_visual
        return self._visuals_by_index.get(segment_index)

    def _chip_geometry_for_segment(
        self,
        segment_index: int,
    ) -> PromptReorderChipGeometry | None:
        """Return live projection-owned chip geometry for one segment."""

        if self._chip_geometry_snapshot is None:
            return None
        return self._chip_geometry_snapshot.geometries_by_chip_index.get(segment_index)

    def _preview_chip_geometry_for_segment(
        self,
        segment_index: int,
    ) -> PromptReorderChipGeometry | None:
        """Return active preview projection-owned chip geometry for one segment."""

        if self._preview_chip_geometry_snapshot is None:
            return None
        return self._preview_chip_geometry_snapshot.geometries_by_chip_index.get(
            segment_index
        )

    def _drop_target_visual_for_target(
        self,
        target: PromptReorderDropTarget | None,
    ) -> _DropTargetVisual | None:
        """Return the current hit-test visual for one active drop target."""

        if target is None:
            return None
        for visual in self._drop_target_visuals:
            if visual.target == target:
                return visual
        return None

    def _log_drop_release_snapshot(
        self,
        *,
        dragged_segment_index: int,
        ending_target: PromptReorderDropTarget | None,
    ) -> None:
        """Log the shadow, target, and preview state at pointer release."""

        shadow_visual = self._landing_shadow.last_landing_preview_visual
        shadow_geometry = self._landing_shadow.last_landing_preview_geometry
        current_preview_visual = self._preview_visuals_by_index.get(
            dragged_segment_index
        )
        current_preview_geometry = self._preview_chip_geometry_for_segment(
            dragged_segment_index
        )
        target_visual = self._drop_target_visual_for_target(ending_target)
        context: dict[str, object] = {
            "dragged_segment_index": dragged_segment_index,
            "has_shadow_visual": shadow_visual is not None,
            "has_shadow_geometry": shadow_geometry is not None,
            "has_current_preview_visual": current_preview_visual is not None,
            "has_current_preview_geometry": current_preview_geometry is not None,
            "has_preview_layout": self._preview_layout_view is not None,
            "last_landing_preview_event_id": (
                self._landing_shadow.last_landing_preview_event_id
            ),
            "ordered_indices": ",".join(
                str(index) for index in self._ordered_segment_indices
            ),
            **self._telemetry.target_context(ending_target, prefix="ending_target"),
            **placement_geometry_context(
                self._active_placement,
                prefix="active_placement",
            ),
        }
        if target_visual is not None:
            context.update(
                self._telemetry.target_visual_context(target_visual, prefix="target")
            )
        if shadow_visual is not None:
            context.update(
                self._telemetry.visual_context(shadow_visual, prefix="shadow")
            )
        if shadow_geometry is not None:
            context.update(
                chip_geometry_context(shadow_geometry, prefix="shadow_geometry")
            )
        if current_preview_visual is not None:
            context.update(
                self._telemetry.visual_context(
                    current_preview_visual, prefix="preview_actual"
                )
            )
        if current_preview_geometry is not None:
            context.update(
                chip_geometry_context(
                    current_preview_geometry,
                    prefix="preview_actual_geometry",
                )
            )
        if shadow_visual is not None and current_preview_visual is not None:
            context.update(
                self._telemetry.visual_delta_context(
                    shadow_visual,
                    current_preview_visual,
                    prefix="shadow_to_preview_actual",
                )
            )
        self._log_interaction_event(
            "drop_commit.release_snapshot",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            **context,
        )

    def _log_post_drop_geometry_checkpoint(
        self,
        *,
        checkpoint: str,
        segment_index: int,
    ) -> None:
        """Log whether the committed chip geometry still matches its last shadow."""

        shadow_visual = self._last_drop_commit_visual
        shadow_geometry = self._last_drop_commit_geometry
        actual_visual = self._visible_visual_for_segment(segment_index)
        actual_geometry = self._chip_geometry_for_segment(segment_index)
        chip = self._chips_by_index.get(segment_index)
        actual_order_index: int | None
        try:
            actual_order_index = self._ordered_segment_indices.index(segment_index)
        except ValueError:
            actual_order_index = None
        context: dict[str, object] = {
            "checkpoint": checkpoint,
            "segment_index": segment_index,
            "actual_order_index": actual_order_index,
            "has_shadow_visual": shadow_visual is not None,
            "has_shadow_geometry": shadow_geometry is not None,
            "has_actual_visual": actual_visual is not None,
            "has_actual_geometry": actual_geometry is not None,
            "has_chip": chip is not None,
            "preview_mode_active": self._preview_mode_active(),
            "has_preview_snapshot": self._preview_snapshot is not None,
            "has_base_drag_snapshot": self._base_drag_snapshot is not None,
            "ordered_indices": ",".join(
                str(index) for index in self._ordered_segment_indices
            ),
            **self._telemetry.target_context(
                self._last_drop_commit_target, prefix="commit_target"
            ),
            **placement_geometry_context(
                self._last_drop_commit_placement,
                prefix="commit_placement",
            ),
        }
        if shadow_visual is not None:
            context.update(
                self._telemetry.visual_context(shadow_visual, prefix="shadow")
            )
        if shadow_geometry is not None:
            context.update(
                chip_geometry_context(shadow_geometry, prefix="shadow_geometry")
            )
        if actual_visual is not None:
            context.update(
                self._telemetry.visual_context(actual_visual, prefix="actual")
            )
        if actual_geometry is not None:
            context.update(
                chip_geometry_context(actual_geometry, prefix="actual_geometry")
            )
        if chip is not None:
            context.update(
                reorder_drag_rect_context(QRectF(chip.geometry()), prefix="chip")
            )
        if shadow_visual is not None and actual_visual is not None:
            context.update(
                self._telemetry.visual_delta_context(
                    shadow_visual,
                    actual_visual,
                    prefix="shadow_to_actual",
                )
            )
        self._log_interaction_event(
            "drop_commit.actual_geometry",
            gesture_id=(
                self._instrumentation_gesture_id or self._last_drop_commit_gesture_id
            ),
            event_id=self._instrumentation_event_id or self._last_drop_commit_event_id,
            **context,
        )
        if shadow_visual is None and self._last_drop_commit_target is not None:
            self._log_reorder_anomaly(
                "anomaly.drop_commit_missing_shadow",
                checkpoint=checkpoint,
                segment_index=segment_index,
                commit_gesture_id=self._last_drop_commit_gesture_id,
                commit_event_id=self._last_drop_commit_event_id,
                **self._telemetry.target_context(
                    self._last_drop_commit_target,
                    prefix="commit_target",
                ),
            )
        if actual_visual is None:
            self._log_reorder_anomaly(
                "anomaly.drop_commit_missing_actual_visual",
                checkpoint=checkpoint,
                segment_index=segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=self._last_drop_commit_gesture_id,
                commit_event_id=self._last_drop_commit_event_id,
            )
            return
        if actual_geometry is None:
            self._log_reorder_anomaly(
                "anomaly.chip_geometry_commit_missing",
                checkpoint=checkpoint,
                segment_index=segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=self._last_drop_commit_gesture_id,
                commit_event_id=self._last_drop_commit_event_id,
            )
            return
        if shadow_geometry is not None and self._chip_geometries_mismatch(
            shadow_geometry,
            actual_geometry,
        ):
            self._log_reorder_anomaly(
                "anomaly.chip_geometry_commit_mismatch",
                checkpoint=checkpoint,
                segment_index=segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=self._last_drop_commit_gesture_id,
                commit_event_id=self._last_drop_commit_event_id,
                **self._telemetry.target_context(
                    self._last_drop_commit_target,
                    prefix="commit_target",
                ),
                **chip_geometry_context(shadow_geometry, prefix="shadow_geometry"),
                **chip_geometry_context(actual_geometry, prefix="actual_geometry"),
            )
        if shadow_visual is not None and self._visuals_mismatch(
            shadow_visual,
            actual_visual,
        ):
            self._log_reorder_anomaly(
                "anomaly.drop_commit_shadow_actual_mismatch",
                checkpoint=checkpoint,
                segment_index=segment_index,
                actual_order_index=actual_order_index,
                commit_gesture_id=self._last_drop_commit_gesture_id,
                commit_event_id=self._last_drop_commit_event_id,
                **self._telemetry.target_context(
                    self._last_drop_commit_target,
                    prefix="commit_target",
                ),
                **self._telemetry.visual_delta_context(
                    shadow_visual,
                    actual_visual,
                    prefix="shadow_to_actual",
                ),
                **self._telemetry.visual_context(shadow_visual, prefix="shadow"),
                **self._telemetry.visual_context(actual_visual, prefix="actual"),
            )

    def _capture_drag_intent_context(
        self,
        chip: _SegmentChip,
        *,
        global_pos: QPoint,
    ) -> None:
        """Capture logical held-chip geometry for pointer drag target resolution."""

        chip_rect = self._drag_intent_source_rect(chip)
        local_pointer = QPointF(self.mapFromGlobal(global_pos))
        self._gesture.capture_drag_intent_context(
            chip_rect=chip_rect,
            local_pointer=local_pointer,
        )

    def _drag_intent_source_rect(self, chip: _SegmentChip) -> QRectF:
        """Return the best available source rect for logical held-chip geometry."""

        chip_rect = QRectF(chip.geometry())
        if not chip_rect.isEmpty():
            return chip_rect

        visual = self._visuals_by_index.get(chip.segment_index)
        if visual is not None and not visual.hotspot_rect.isEmpty():
            return QRectF(visual.hotspot_rect)

        fallback_size = chip.sizeHint()
        if fallback_size.isEmpty():
            fallback_size = chip.size()
        return QRectF(
            QPointF(chip.pos()),
            QSizeF(
                max(1.0, float(fallback_size.width())),
                max(1.0, float(fallback_size.height())),
            ),
        )

    def _clear_drag_intent_context(self) -> None:
        """Clear logical held-chip geometry captured for pointer drag targeting."""

        self._gesture.clear_drag_intent_context()

    def _clear_last_drop_commit_context(self) -> None:
        """Clear the saved release geometry after post-drop diagnostics consume it."""

        self._last_drop_commit_visual = None
        self._last_drop_commit_geometry = None
        self._last_drop_commit_target = None
        self._last_drop_commit_placement = None
        self._last_drop_commit_segment_index = None
        self._last_drop_commit_gesture_id = None
        self._last_drop_commit_event_id = None

    def _autoscroll_context(self) -> PromptReorderAutoscrollContext:
        """Return prompt-safe diagnostic identity for autoscroll ticks."""

        return PromptReorderAutoscrollContext(
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
        )

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Apply the latest coalesced autoscroll geometry invalidation."""

        invalidation = self._pending_autoscroll_invalidation
        if invalidation is None:
            return False
        self._pending_autoscroll_invalidation = None
        self._settle_chip_animations(reason=f"autoscroll_flush:{reason}")
        self._instrumentation_autoscroll_flush_count += 1
        self.refresh_geometry(reason=reason)
        before_target = self._gesture.state.active_drop_target
        self._update_drop_target_from_global_position(
            invalidation.global_position,
            emit_preview_changed=False,
        )
        if before_target != self._gesture.state.active_drop_target:
            self._instrumentation_autoscroll_target_refresh_count += 1
        self._log_interaction_event(
            "autoscroll.invalidation_flushed",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            reason=reason,
            direction=invalidation.direction,
            previous_scroll_position=invalidation.previous_scroll_position,
            next_scroll_position=invalidation.next_scroll_position,
            invalidation_index=invalidation.invalidation_index,
            target_changed=before_target != self._gesture.state.active_drop_target,
        )
        return True

    def _handle_autoscroll_step(
        self,
        invalidation: PromptReorderAutoscrollInvalidation,
    ) -> None:
        """Record scroll invalidation and schedule coalesced preview refresh."""

        if self._pending_autoscroll_invalidation is not None:
            self._instrumentation_autoscroll_coalesced_count += 1
        self._settle_chip_animations(reason="autoscroll_step")
        self._pending_autoscroll_invalidation = invalidation
        self._instrumentation_autoscroll_schedule_count += 1
        self._last_overlay_refresh_geometry_key = None
        self._emit_preview_layout_changed()

    def _clear_pending_autoscroll_invalidation(self) -> None:
        """Drop pending autoscroll geometry work for a finished drag gesture."""

        self._pending_autoscroll_invalidation = None

    def _build_visuals_if_needed(self, *, reason: str) -> dict[int, PromptChipVisual]:
        """Reuse live chip visuals unless source, viewport, or scroll geometry changed."""

        geometry_key = self._live_visual_geometry_key()
        if (
            geometry_key == self._last_live_visual_geometry_key
            and self._visuals_by_index
            and self._live_visual_snapshots_by_index
        ):
            self._log_interaction_event(
                "live_visuals.skipped_unchanged_geometry",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                reason=reason,
                visual_count=len(self._visuals_by_index),
                cache_size=0,
            )
            return self._visuals_by_index

        self._last_live_visual_geometry_key = geometry_key
        return self._build_visuals(reason=reason)

    def _live_visual_geometry_key(self) -> _LiveVisualGeometryKey:
        """Return the current geometry identity for live chip visual fragments."""

        scrollbar = self._editor.verticalScrollBar()
        segment_ranges = tuple(
            sorted(
                (
                    segment.index,
                    segment.selection_start,
                    segment.selection_end,
                )
                for segment in self._segments_by_index.values()
            )
        )
        source_text = (
            "" if self._document_view is None else self._document_view.source_text
        )
        return reorder_live_visual_geometry_key(
            source_text=source_text,
            segment_ranges=segment_ranges,
            content_left=self._content_rect.left(),
            content_top=self._content_rect.top(),
            content_width=self._content_rect.width(),
            scroll_offset=scrollbar.value(),
        )

    def _build_visuals(self, *, reason: str) -> dict[int, PromptChipVisual]:
        """Project every prompt segment into semantic chip geometry."""

        total_started_at = reorder_drag_started_at()
        layout_view = self._current_layout_view
        if layout_view is None:
            self._chip_geometry_snapshot = None
            return {}
        snapshot = self._editor.reorder_live_chip_geometry_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=self._live_chip_rendered_ranges_by_index(),
            chip_owned_ranges_by_index=self._live_chip_owned_ranges_by_index(),
        )
        self._chip_geometry_snapshot = snapshot
        self._geometry.live_chip_geometry_snapshot = snapshot
        if len(snapshot.geometries_by_chip_index) != len(self._segments_by_index):
            self._log_reorder_anomaly(
                "anomaly.chip_geometry_paint_count_mismatch",
                expected_chip_count=len(self._segments_by_index),
                chip_geometry_count=len(snapshot.geometries_by_chip_index),
                **chip_geometry_snapshot_context(snapshot),
            )
        visuals = {
            chip_index: prompt_reorder_visual_for_chip_geometry(geometry)
            for chip_index, geometry in snapshot.geometries_by_chip_index.items()
        }
        self._live_visual_snapshots_by_index = self._chip_visual_snapshots_from_projection(
            projection_snapshots=self._editor.reorder_live_chip_projection_paint_snapshots(
                chip_geometry_snapshot=snapshot,
                chip_owned_ranges_by_index=self._live_chip_owned_ranges_by_index(),
            ),
            visuals_by_index=visuals,
        )
        self._visual_snapshot_cache.store_all(self._live_visual_snapshots_by_index)
        total_elapsed_ms = self._log_interaction_timing(
            "live_visuals.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            reason=reason,
            segment_count=len(self._segments_by_index),
            visual_count=len(visuals),
            reused_visual_count=0,
            rebuilt_visual_count=len(visuals),
            fragment_query_count=0,
            fragment_total_count=0,
            split_bubble_count=sum(
                1 for visual in visuals.values() if len(visual.bubble_rects) > 1
            ),
            slowest_segment_index=None,
            slowest_fragment_query_ms="0.000",
            **chip_geometry_snapshot_context(snapshot),
        )
        self._instrumentation_max_live_visuals_ms = max(
            self._instrumentation_max_live_visuals_ms,
            total_elapsed_ms,
        )
        self._log_slow_path_if_needed(
            "slow.live_visuals",
            elapsed_ms=total_elapsed_ms,
            threshold_ms=_SLOW_LIVE_VISUALS_MS,
            reason=reason,
            segment_count=len(self._segments_by_index),
            reused_visual_count=0,
            rebuilt_visual_count=len(visuals),
            slowest_segment_index=None,
        )
        return visuals

    def _live_chip_rendered_ranges_by_index(self) -> dict[int, tuple[int, int]]:
        """Return live source ranges keyed by semantic reorder chip index."""

        return {
            segment.index: (segment.selection_start, segment.selection_end)
            for segment in self._segments_by_index.values()
        }

    def _live_chip_owned_ranges_by_index(
        self,
    ) -> dict[int, tuple[tuple[int, int], ...]]:
        """Return live owned source ranges keyed by semantic reorder chip index."""

        return {
            segment.index: ((segment.selection_start, segment.selection_end),)
            for segment in self._segments_by_index.values()
        }

    def _chip_visual_snapshots_from_projection(
        self,
        *,
        projection_snapshots: dict[int, PromptReorderProjectionPaintSnapshot],
        visuals_by_index: dict[int, PromptChipVisual],
    ) -> dict[int, PromptReorderChipVisualSnapshot]:
        """Bind projection paint snapshots to overlay visuals for complete chips."""

        visual_snapshots: dict[int, PromptReorderChipVisualSnapshot] = {}
        for segment_index, projection_snapshot in projection_snapshots.items():
            visual = visuals_by_index.get(segment_index)
            if visual is None:
                continue
            visual_snapshots[segment_index] = PromptReorderChipVisualSnapshot(
                segment_index=segment_index,
                visual=visual,
                projection_snapshot=projection_snapshot,
            )
        return visual_snapshots

    def _preview_mode_active(self) -> bool:
        """Return whether the overlay should show movable preview chips."""

        return self._layout_for_painted_preview() is not None

    def _landing_shadow_request(self) -> PromptReorderLandingShadowRequest:
        """Return current overlay state needed by the landing-shadow presenter."""

        dragged_segment_index = self._gesture.state.dragged_segment_index
        return PromptReorderLandingShadowRequest(
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            dragged_segment_index=dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            active_placement=self._active_placement,
            dragged_segment=(
                None
                if dragged_segment_index is None
                else self._segments_by_index.get(dragged_segment_index)
            ),
            content_rect=QRectF(self._content_rect),
            overlay_rect=QRectF(self.rect()),
            preview_layout_active=self._preview_mode_active(),
            preview_snapshot_available=self._preview_snapshot is not None,
            preview_visual_count=len(self._preview_visuals_by_index),
            landing_geometry=(
                None
                if dragged_segment_index is None
                else self._preview_chip_geometry_for_segment(dragged_segment_index)
            ),
            target_visual=self._drop_target_visual_for_target(
                self._gesture.state.active_drop_target
            ),
            preview_geometry_target_identity=self._preview_geometry_target_identity,
            expected_preview_target_identity=(
                self._preview_target_identity_for_active_target()
            ),
            preview_target_identity_matches=(
                self._preview_target_identity_matches_active_target()
            ),
        )

    def _sync_reorder_view_state(self, *, reason: str) -> None:
        """Publish prepared reorder chrome to the passive view."""

        state = self._reorder_view_render_state()
        self._sync_reorder_overlay_suppression(state)
        self._view.set_render_state(state)

    def _sync_reorder_overlay_suppression(
        self,
        state: PromptReorderViewRenderState,
    ) -> None:
        """Suppress document chips whose preview paint is owned by the overlay."""

        if not state.preview_active:
            self._set_reorder_overlay_suppression(frozenset())
            return
        requested_indices = frozenset(
            chip.segment_index for chip in state.preview_chips
        )
        self._set_reorder_overlay_suppression(requested_indices)

    def _set_reorder_overlay_suppression(self, indices: frozenset[int]) -> None:
        """Publish suppression only when the raster-backed set changes."""

        if indices == self._last_suppressed_chip_indices:
            return
        self._last_suppressed_chip_indices = indices
        self._editor.set_reorder_overlay_suppressed_chip_indices(indices)

    def _reorder_view_render_state(self) -> PromptReorderViewRenderState:
        """Delegate passive render-state construction to the reorder view owner."""

        preview_active = self._preview_mode_active()
        landing_preview = None
        if preview_active:
            landing_result = self._landing_shadow.landing_preview_paint_state(
                self._landing_shadow_request(),
                visual_style=self._visual_style,
            )
            landing_preview = landing_result.paint_state
            self._active_placement = landing_result.active_placement
            self._geometry.active_placement = self._active_placement
        live_geometries = (
            {}
            if self._chip_geometry_snapshot is None
            else self._chip_geometry_snapshot.geometries_by_chip_index
        )
        preview_geometries = (
            {}
            if self._preview_chip_geometry_snapshot is None
            else self._preview_chip_geometry_snapshot.geometries_by_chip_index
        )
        paint_rect_overrides = self._animation_presenter.paint_rect_overrides()
        paint_rect_overrides.update(self._held_chip_presenter.paint_rect_overrides())
        device_pixel_ratio = self._view.devicePixelRatioF()
        preview_styles = self._chip_styles_by_index(tuple(self.preview_chip_indices()))
        live_raster_entries = (
            {}
            if preview_active
            else self._raster_entries_for_render_state(
                cache_name="live",
                snapshots_by_index=self._live_visual_snapshots_by_index,
                styles_by_index=self._chip_styles_by_index(
                    self._initial_ordered_indices
                ),
                device_pixel_ratio=device_pixel_ratio,
            )
        )
        preview_raster_entries = (
            self._raster_entries_for_render_state(
                cache_name="preview",
                snapshots_by_index=self._preview_visual_snapshots_by_index,
                styles_by_index=preview_styles,
                device_pixel_ratio=device_pixel_ratio,
            )
            if preview_active
            else {}
        )
        state = prompt_reorder_view_render_state(
            PromptReorderViewRenderInput(
                visual_style=self._visual_style,
                preview_active=preview_active,
                live_ordered_segment_indices=self._initial_ordered_indices,
                preview_ordered_segment_indices=tuple(self.preview_chip_indices()),
                live_geometries_by_index=live_geometries,
                preview_geometries_by_index=preview_geometries,
                live_visuals_by_index=self._visuals_by_index,
                preview_visuals_by_index=self._preview_visuals_by_index,
                dragged_segment_index=self._gesture.state.dragged_segment_index,
                hovered_segment_index=self._gesture.state.hovered_segment_index,
                active_segment_index=self._gesture.state.active_segment_index,
                live_visual_snapshots_by_index=self._live_visual_snapshots_by_index,
                preview_visual_snapshots_by_index=(
                    self._preview_visual_snapshots_by_index
                ),
                live_raster_entries_by_index=live_raster_entries,
                preview_raster_entries_by_index=preview_raster_entries,
                marker_rect=self._insertion_marker_rect(),
                landing_preview=landing_preview,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                paint_rect_overrides_by_index=paint_rect_overrides,
            )
        )
        return state

    def _raster_entries_for_render_state(
        self,
        *,
        cache_name: str,
        snapshots_by_index: dict[int, PromptReorderChipVisualSnapshot],
        styles_by_index: dict[int, PromptChipPaintStyle],
        device_pixel_ratio: float,
    ) -> dict[int, ReorderRasterEntry]:
        """Return raster entries, reusing an unchanged render-state mapping."""

        render_key = self._raster_entries_render_key(
            snapshots_by_index=snapshots_by_index,
            styles_by_index=styles_by_index,
            device_pixel_ratio=device_pixel_ratio,
        )
        if cache_name == "preview":
            if render_key == self._preview_raster_entries_render_key:
                self._instrumentation_raster_entries_render_cache_hit_count += 1
                return self._preview_raster_entries_by_index
            entries = self._raster_cache.entries_for_snapshots(
                snapshots_by_index=snapshots_by_index,
                styles_by_index=styles_by_index,
                device_pixel_ratio=device_pixel_ratio,
            )
            self._instrumentation_raster_entries_render_cache_miss_count += 1
            self._preview_raster_entries_render_key = render_key
            self._preview_raster_entries_by_index = entries
            return entries

        if render_key == self._live_raster_entries_render_key:
            self._instrumentation_raster_entries_render_cache_hit_count += 1
            return self._live_raster_entries_by_index
        entries = self._raster_cache.entries_for_snapshots(
            snapshots_by_index=snapshots_by_index,
            styles_by_index=styles_by_index,
            device_pixel_ratio=device_pixel_ratio,
        )
        self._instrumentation_raster_entries_render_cache_miss_count += 1
        self._live_raster_entries_render_key = render_key
        self._live_raster_entries_by_index = entries
        return entries

    def _raster_entries_render_key(
        self,
        *,
        snapshots_by_index: dict[int, PromptReorderChipVisualSnapshot],
        styles_by_index: dict[int, PromptChipPaintStyle],
        device_pixel_ratio: float,
    ) -> tuple[object, ...]:
        """Return an exact identity for one render-state raster-entry mapping."""

        return (
            device_pixel_ratio,
            tuple(
                (
                    segment_index,
                    id(snapshot),
                    self._paint_style_render_key(styles_by_index[segment_index]),
                )
                for segment_index, snapshot in sorted(snapshots_by_index.items())
                if segment_index in styles_by_index
            ),
        )

    def _paint_style_render_key(
        self,
        style: PromptChipPaintStyle,
    ) -> tuple[int, int, bool, float, float]:
        """Return the raster-relevant values for one chip paint style."""

        return (
            style.fill_color.rgba(),
            style.border_color.rgba(),
            style.outline_only,
            style.outline_width,
            style.opacity,
        )

    def _chip_styles_by_index(
        self,
        segment_indices: tuple[int, ...],
    ) -> dict[int, PromptChipPaintStyle]:
        """Return prepared chip styles keyed by segment index for rasterization."""

        return {
            segment_index: self._visual_style.paint_style_for_segment(
                segment_index,
                dragged_segment_index=self._gesture.state.dragged_segment_index,
                hovered_segment_index=self._gesture.state.hovered_segment_index,
                active_segment_index=self._gesture.state.active_segment_index,
            )
            for segment_index in segment_indices
        }

    def _update_preview_layout(self) -> None:
        """Refresh the typed reorder layout state tracked by the overlay."""

        if self._document_view is None:
            return
        self._geometry.document_view = self._document_view
        self._geometry.current_layout_view = self._current_layout_view
        self._geometry.current_reorder_state = self._current_reorder_state
        self._geometry.base_drag_layout_view = self._base_drag_layout_view
        self._geometry.base_drag_reorder_state = self._base_drag_reorder_state
        self._geometry.initial_ordered_indices = self._initial_ordered_indices
        self._geometry.update_preview_layout(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
        )
        self._preview_layout_view = self._geometry.preview_layout_view
        self._preview_reorder_state = self._geometry.preview_reorder_state
        self._base_drag_reorder_state = self._geometry.base_drag_reorder_state
        self._preview_layout_target_identity = (
            self._geometry.preview_layout_target_identity
        )
        self._ordered_segment_indices = list(self._geometry.ordered_segment_indices)
        self._drag_proxy.raise_()

    def _refresh_preview_geometry(self) -> None:
        """Refresh preview visuals and drop targets from the controller-owned snapshot."""

        total_started_at = reorder_drag_started_at()
        self._instrumentation_preview_geometry_full_count += 1
        preview_snapshot = self._preview_snapshot
        previous_preview_visuals = self._preview_visuals_by_index
        previous_base_drag_visuals = self._base_drag_visuals_by_index
        self._geometry.preview_snapshot = self._preview_snapshot
        self._geometry.base_drag_snapshot = self._base_drag_snapshot
        self._geometry.preview_layout_view = self._preview_layout_view
        self._geometry.preview_reorder_state = self._preview_reorder_state
        self._geometry.base_drag_layout_view = self._base_drag_layout_view
        self._geometry.base_drag_reorder_state = self._base_drag_reorder_state
        self._geometry.preview_layout_target_identity = (
            self._preview_layout_target_identity
        )
        refresh = self._geometry.refresh_preview_geometry(
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            active_target=self._gesture.state.active_drop_target,
            viewport_identity=self._overlay_position_geometry_key(),
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
        )
        next_preview_visuals: dict[int, PromptChipVisual] = {}
        preview_hit_count = 0
        preview_miss_count = 0
        if refresh.preview_chip_snapshot is not None:
            phase_started_at = reorder_drag_started_at()
            preview_result = self._visuals_from_chip_geometry_snapshot(
                refresh.preview_chip_snapshot,
                cache_namespace="preview",
                previous_snapshot=refresh.previous_preview_chip_snapshot,
                previous_visuals=previous_preview_visuals,
            )
            next_preview_visuals = preview_result.visuals
            preview_hit_count = preview_result.cache_hit_count
            preview_miss_count = preview_result.cache_miss_count
            self._instrumentation_preview_geometry_reused_chip_count += (
                preview_result.cache_hit_count
            )
            self._instrumentation_preview_geometry_rebuilt_chip_count += (
                preview_result.cache_miss_count
            )
            self._instrumentation_preview_geometry_reuse_rejected_count += (
                preview_result.reuse_rejected_count
            )
            self._log_interaction_timing(
                "preview_geometry.preview_visuals",
                started_at=phase_started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                visual_count=len(next_preview_visuals),
                reused_visual_count=preview_hit_count,
                rebuilt_visual_count=preview_miss_count,
                reuse_rejected_count=preview_result.reuse_rejected_count,
                changed_visual_count=self._changed_visual_count(
                    previous_preview_visuals,
                    next_preview_visuals,
                ),
                unchanged_visual_count=self._unchanged_visual_count(
                    previous_preview_visuals,
                    next_preview_visuals,
                ),
            )

        next_base_drag_visuals = (
            self._base_drag_visuals_by_index
            if refresh.base_drag_geometry_reused
            else {}
        )
        base_hit_count = 0
        base_miss_count = 0
        if refresh.base_drag_geometry_reused:
            base_hit_count = len(next_base_drag_visuals)
            self._instrumentation_base_drag_geometry_reuse_count += 1
        elif refresh.base_drag_chip_snapshot is not None:
            phase_started_at = reorder_drag_started_at()
            base_result = self._visuals_from_chip_geometry_snapshot(
                refresh.base_drag_chip_snapshot,
                cache_namespace="base_drag",
                previous_snapshot=refresh.previous_base_drag_chip_snapshot,
                previous_visuals=previous_base_drag_visuals,
            )
            next_base_drag_visuals = base_result.visuals
            base_hit_count = base_result.cache_hit_count
            base_miss_count = base_result.cache_miss_count
            self._instrumentation_base_drag_geometry_rebuild_count += 1
            self._log_interaction_timing(
                "preview_geometry.base_drag_visuals",
                started_at=phase_started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                visual_count=len(next_base_drag_visuals),
                reused_visual_count=base_hit_count,
                rebuilt_visual_count=base_miss_count,
                reuse_rejected_count=base_result.reuse_rejected_count,
                changed_visual_count=self._changed_visual_count(
                    previous_base_drag_visuals,
                    next_base_drag_visuals,
                ),
                unchanged_visual_count=self._unchanged_visual_count(
                    previous_base_drag_visuals,
                    next_base_drag_visuals,
                ),
            )
            self._base_drag_visuals_by_index = next_base_drag_visuals

        self._preview_visuals_by_index = next_preview_visuals
        self._base_drag_visuals_by_index = next_base_drag_visuals
        self._preview_chip_geometry_snapshot = refresh.preview_chip_snapshot
        self._base_drag_chip_geometry_snapshot = refresh.base_drag_chip_snapshot
        if refresh.preview_chip_snapshot is not None and preview_snapshot is not None:
            self._preview_visual_snapshots_by_index = (
                self._chip_visual_snapshots_from_projection(
                    projection_snapshots=(
                        self._editor.reorder_preview_chip_projection_paint_snapshots(
                            chip_geometry_snapshot=refresh.preview_chip_snapshot,
                            chip_owned_ranges_by_index=(
                                preview_snapshot.chip_owned_ranges_by_index
                            ),
                        )
                    ),
                    visuals_by_index=next_preview_visuals,
                )
            )
            self._visual_snapshot_cache.store_all(
                self._preview_visual_snapshots_by_index
            )
        else:
            self._preview_visual_snapshots_by_index = {}
        self._preview_geometry_target_identity = refresh.preview_geometry_identity
        self._placement_snapshot = refresh.placement_snapshot
        self._active_placement = self._geometry.active_placement
        self._drop_target_visuals = refresh.drop_target_visuals
        self._drop_target_lanes = refresh.drop_target_lanes
        self._active_placement = (
            self._landing_shadow.attach_expected_landing_to_active_placement(
                self._landing_shadow_request()
            )
        )
        self._geometry.active_placement = self._active_placement
        self._landing_shadow.mark_initial_landing_shadow_ready(
            self._landing_shadow_request()
        )
        elapsed_ms = self._log_interaction_timing(
            "preview_geometry.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            preview_visual_count=len(next_preview_visuals),
            base_drag_visual_count=len(next_base_drag_visuals),
            visual_target_count=len(refresh.drop_target_visuals),
            lane_count=len(refresh.drop_target_lanes),
            preview_reused_visual_count=preview_hit_count,
            preview_rebuilt_visual_count=preview_miss_count,
            base_reused_visual_count=base_hit_count,
            base_rebuilt_visual_count=base_miss_count,
            base_drag_geometry_reused=refresh.base_drag_geometry_reused,
        )
        self._log_interaction_event(
            "preview_geometry.full_geometry_applied",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            elapsed_ms=f"{elapsed_ms:.3f}",
            has_preview_snapshot=preview_snapshot is not None,
            has_base_drag_snapshot=self._base_drag_snapshot is not None,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
        )
        if elapsed_ms >= _SLOW_LIVE_VISUALS_MS:
            self._log_interaction_event(
                "budget.preview_geometry_exceeded",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_LIVE_VISUALS_MS:.3f}",
                has_preview_snapshot=preview_snapshot is not None,
                has_base_drag_snapshot=self._base_drag_snapshot is not None,
            )

    def _visuals_from_chip_geometry_snapshot(
        self,
        snapshot: PromptReorderChipGeometrySnapshot,
        *,
        cache_namespace: str,
        previous_snapshot: PromptReorderChipGeometrySnapshot | None,
        previous_visuals: dict[int, PromptChipVisual],
    ) -> _VisualBuildResult:
        """Build chip visuals from one semantic geometry snapshot."""

        total_started_at = reorder_drag_started_at()
        visuals: dict[int, PromptChipVisual] = {}
        reused_visual_count = 0
        rebuilt_visual_count = 0
        reuse_rejected_count = 0
        previous_geometries = (
            {}
            if previous_snapshot is None
            else previous_snapshot.geometries_by_chip_index
        )
        for chip_index, geometry in snapshot.geometries_by_chip_index.items():
            previous_geometry = previous_geometries.get(chip_index)
            previous_visual = previous_visuals.get(chip_index)
            if (
                previous_geometry is not None
                and previous_visual is not None
                and chip_geometry_visual_reuse_key(previous_geometry)
                == chip_geometry_visual_reuse_key(geometry)
            ):
                visuals[chip_index] = previous_visual
                reused_visual_count += 1
                continue
            if previous_geometry is not None or previous_visual is not None:
                reuse_rejected_count += 1
            visuals[chip_index] = prompt_reorder_visual_for_chip_geometry(geometry)
            rebuilt_visual_count += 1
        self._log_interaction_timing(
            "visuals.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            namespace=cache_namespace,
            requested_visual_count=len(snapshot.ordered_chip_indices),
            built_visual_count=len(visuals),
            reused_visual_count=reused_visual_count,
            rebuilt_visual_count=rebuilt_visual_count,
            reuse_rejected_count=reuse_rejected_count,
            **chip_geometry_snapshot_context(snapshot),
        )
        return _VisualBuildResult(
            visuals=visuals,
            cache_hit_count=reused_visual_count,
            cache_miss_count=rebuilt_visual_count,
            reuse_rejected_count=reuse_rejected_count,
        )

    @staticmethod
    def _changed_visual_count(
        previous_visuals: dict[int, PromptChipVisual],
        next_visuals: dict[int, PromptChipVisual],
    ) -> int:
        """Return how many chip visuals changed across one refresh."""

        changed = sum(
            1
            for segment_index, visual in next_visuals.items()
            if previous_visuals.get(segment_index) != visual
        )
        removed = len(set(previous_visuals) - set(next_visuals))
        return changed + removed

    @staticmethod
    def _unchanged_visual_count(
        previous_visuals: dict[int, PromptChipVisual],
        next_visuals: dict[int, PromptChipVisual],
    ) -> int:
        """Return how many chip visuals stayed identical across one refresh."""

        return sum(
            1
            for segment_index, visual in next_visuals.items()
            if previous_visuals.get(segment_index) == visual
        )

    def _layout_for_painted_preview(self) -> PromptReorderLayoutView | None:
        """Return the layout currently represented by the surface-owned preview state."""

        if self._gesture.state.dragged_segment_index is not None:
            return self._preview_layout_view
        if (
            self._gesture.state.active_segment_index is not None
            and self._gesture.state.active_drop_target is not None
        ):
            return self._current_layout_view
        if self.has_reordered():
            return self._current_layout_view
        return None

    def _update_chip_geometry(self) -> None:
        """Resize and restack transparent hotspots from the latest fragment geometry."""

        started_at = reorder_drag_started_at()
        preview_positioned_count = 0
        live_positioned_count = 0
        hidden_count = 0
        for segment_index, chip in self._chips_by_index.items():
            preview_visual = self._preview_visuals_by_index.get(segment_index)
            if (
                self._preview_mode_active()
                and preview_visual is not None
                and segment_index != self._gesture.state.dragged_segment_index
            ):
                chip.setGeometry(preview_visual.hotspot_rect)
                chip.show()
                chip.raise_()
                preview_positioned_count += 1
                continue
            if segment_index == self._gesture.state.dragged_segment_index:
                chip.raise_()
                continue

            visual = self._visuals_by_index.get(segment_index)
            if visual is None:
                chip.hide()
                hidden_count += 1
                continue
            chip.setGeometry(visual.hotspot_rect)
            chip.show()
            chip.raise_()
            live_positioned_count += 1
        self._drag_proxy.raise_()
        self._update_chip_states()
        self._log_interaction_timing(
            "chip_geometry.update",
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            chip_count=len(self._chips_by_index),
            preview_positioned_count=preview_positioned_count,
            live_positioned_count=live_positioned_count,
            hidden_count=hidden_count,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
        )

    def _update_chip_states(self) -> None:
        """Push active, hover, and drag state onto the transparent hotspots."""

        detailed_states: list[str] = []
        for chip_state in prompt_reorder_chip_widget_states(
            tuple(self._chips_by_index),
            visual_style=self._visual_style,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            hovered_segment_index=self._gesture.state.hovered_segment_index,
            active_segment_index=self._gesture.state.active_segment_index,
            pressed_segment_index=self._gesture.state.pressed_segment_index,
        ):
            chip = self._chips_by_index[chip_state.segment_index]
            chip.set_visual_state(
                active=chip_state.active,
                dragging=chip_state.dragging,
                hovered=chip_state.hovered,
            )
            chip.setCursor(chip_state.cursor_shape)
            if (
                chip_state.active
                or chip_state.dragging
                or chip_state.hovered
                or chip_state.pressed
            ):
                fill_color = chip_state.style.fill_color
                border_color = chip_state.style.border_color
                detailed_states.append(
                    (
                        f"{chip_state.segment_index}:active={chip_state.active}:"
                        f"dragging={chip_state.dragging}:"
                        f"hovered={chip_state.hovered}:"
                        f"pressed={chip_state.pressed}:"
                        f"fill_a={fill_color.alpha()}:border_a={border_color.alpha()}"
                    )
                )
                if border_color.alpha() == 0:
                    self._log_reorder_anomaly(
                        "anomaly.paint_style_transparent_border",
                        segment_index=chip_state.segment_index,
                        active=chip_state.active,
                        dragging=chip_state.dragging,
                        hovered=chip_state.hovered,
                        pressed=chip_state.pressed,
                        **reorder_drag_color_context(
                            border_color,
                            prefix="border",
                        ),
                    )
        self._log_interaction_event(
            "chip_state.update",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            active_segment_index=self._gesture.state.active_segment_index,
            hovered_segment_index=self._gesture.state.hovered_segment_index,
            pressed_segment_index=self._gesture.state.pressed_segment_index,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            detailed_states=";".join(detailed_states),
        )

    def _update_drop_target_from_global_position(
        self,
        global_pos: QPoint,
        *,
        emit_preview_changed: bool = True,
    ) -> None:
        """Resolve the current typed row/gap target from held-chip drag geometry."""

        if self._gesture.state.dragged_segment_index is None:
            return

        total_started_at = reorder_drag_started_at()
        previous_target = self._gesture.state.active_drop_target
        drag_rect = self._drag_intent_rect_from_global_position(global_pos)
        phase_started_at = reorder_drag_started_at()
        resolution = self._drop_target_tracker.resolve(
            PromptReorderDropTargetResolverInput(
                drop_lanes=self._drop_target_lanes,
                target_visuals=self._drop_target_visuals,
                active_target=previous_target,
                drag_rect=drag_rect,
                geometry_generation_id=self._instrumentation_work_unit_id,
                placement_snapshot=self._placement_snapshot,
                active_placement=self._active_placement,
            ),
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
        )
        self._active_placement = resolution.active_placement
        self._geometry.active_placement = self._active_placement
        next_drop_target = resolution.target
        target_changed = resolution.changed
        pointer_sample = self._telemetry.should_log_pointer_event(
            move_count=self._instrumentation_drag_move_count,
            target_changed=target_changed,
        )
        if pointer_sample:
            resolve_elapsed_ms = self._log_interaction_timing(
                "drop_target.resolve",
                started_at=phase_started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                previous_target_kind=reorder_drag_target_kind(previous_target),
                next_target_kind=reorder_drag_target_kind(next_drop_target),
                target_changed=target_changed,
                lane_count=len(self._drop_target_lanes),
                visual_target_count=len(self._drop_target_visuals),
                **reorder_drag_rect_context(drag_rect, prefix="intent"),
            )
        else:
            resolve_elapsed_ms = (time.perf_counter() - phase_started_at) * 1000.0
        if resolution.no_lane:
            self._instrumentation_no_lane_count += 1
            if self._base_drag_layout_view is not None:
                self._log_reorder_anomaly(
                    "anomaly.no_drop_lanes_after_base_drag_ready",
                    base_row_count=len(self._base_drag_layout_view.rows),
                    base_gap_count=len(self._base_drag_layout_view.gaps),
                    has_base_snapshot=self._base_drag_snapshot is not None,
                    **reorder_drag_rect_context(drag_rect, prefix="intent"),
                )
        if not target_changed:
            self._instrumentation_drop_target_no_change_count += 1
            if pointer_sample:
                self._log_interaction_event(
                    "drop_target.no_change_fast_path",
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=self._instrumentation_event_id,
                    active_target_kind=reorder_drag_target_kind(
                        self._gesture.state.active_drop_target
                    ),
                    resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
                )
                self._log_interaction_timing(
                    "drop_target.total",
                    started_at=total_started_at,
                    gesture_id=self._instrumentation_gesture_id,
                    event_id=self._instrumentation_event_id,
                    target_changed=False,
                    active_target_kind=reorder_drag_target_kind(
                        self._gesture.state.active_drop_target
                    ),
                    resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
                )
            return

        self._instrumentation_drop_target_changed_count += 1
        self._log_interaction_event(
            "drop_target.changed_rebuild_path",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            previous_target_kind=reorder_drag_target_kind(previous_target),
            next_target_kind=reorder_drag_target_kind(next_drop_target),
            resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
        )
        self._gesture.set_active_drop_target(next_drop_target)
        dragged_segment_index = self._gesture.state.dragged_segment_index
        if dragged_segment_index is not None:
            self._mark_reorder_displacement_target_changed(
                ReorderDisplacementIntent(
                    source="pointer",
                    held_segment_index=dragged_segment_index,
                    target=next_drop_target,
                    pointer_global_pos=self._gesture.state.last_drag_global_position,
                    reason="pointer_target_changed",
                )
            )
        phase_started_at = reorder_drag_started_at()
        self._update_preview_layout()
        self._log_interaction_timing(
            "drop_target.changed.preview_layout",
            started_at=phase_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            ordered_count=len(self._ordered_segment_indices),
        )
        if (
            self._gesture.state.active_drop_target is not None
            and self._preview_layout_view is None
        ):
            self._log_reorder_anomaly(
                "anomaly.target_changed_without_preview_update",
                previous_target_kind=reorder_drag_target_kind(previous_target),
                **self._telemetry.target_context(
                    self._gesture.state.active_drop_target, prefix="active_target"
                ),
            )
        if emit_preview_changed:
            phase_started_at = reorder_drag_started_at()
            self._emit_preview_layout_changed()
            self._log_interaction_timing(
                "drop_target.changed.preview_signal",
                started_at=phase_started_at,
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                active_target_kind=reorder_drag_target_kind(
                    self._gesture.state.active_drop_target
                ),
            )
        self._log_interaction_event(
            "preview_state.surface_sync_requested",
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            has_preview_snapshot=self._preview_snapshot is not None,
            has_current_preview_geometry=(
                self._gesture.state.dragged_segment_index is not None
                and self._preview_chip_geometry_for_segment(
                    self._gesture.state.dragged_segment_index
                )
                is not None
            ),
            has_last_valid_shadow=(
                self._landing_shadow.last_landing_preview_geometry is not None
            ),
        )
        self._log_interaction_timing(
            "drop_target.total",
            started_at=total_started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            target_changed=True,
            active_target_kind=reorder_drag_target_kind(
                self._gesture.state.active_drop_target
            ),
            resolve_elapsed_ms=f"{resolve_elapsed_ms:.3f}",
            ordered_count=len(self._ordered_segment_indices),
        )

    def _drag_intent_rect_from_global_position(self, global_pos: QPoint) -> QRectF:
        """Return the logical held-chip rect used for drop-target resolution."""

        local_pointer = QPointF(self.mapFromGlobal(global_pos))
        size = self._gesture.state.drag_intent_size
        if size is None or size.isEmpty():
            size = QSizeF(1.0, 1.0)
        grab_offset = self._gesture.state.drag_grab_offset
        if grab_offset is None:
            grab_offset = QPointF(size.width() / 2.0, size.height() / 2.0)

        intent_rect = QRectF(local_pointer - grab_offset, size)
        self._gesture.set_last_drag_intent_rect(intent_rect)
        return intent_rect

    def _capture_held_shadow_geometry(self, chip: _SegmentChip) -> None:
        """Delegate held-chip chrome capture to the landing-shadow presenter."""

        base_geometry = None
        if self._base_drag_chip_geometry_snapshot is not None:
            base_geometry = (
                self._base_drag_chip_geometry_snapshot.geometries_by_chip_index.get(
                    chip.segment_index
                )
            )
        proxy_size = self._drag_proxy.size()
        self._landing_shadow.capture_held_shadow(
            PromptReorderHeldShadowCaptureInput(
                chip_index=chip.segment_index,
                live_geometry=self._chip_geometry_for_segment(chip.segment_index),
                base_drag_geometry=base_geometry,
                live_visual=self._visuals_by_index.get(chip.segment_index),
                chip_size=chip.geometry().size(),
                proxy_size=proxy_size,
                proxy_size_hint=self._drag_proxy.sizeHint(),
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
            )
        )

    def _placement_owned_landing_geometry(
        self,
        *,
        reason: str,
    ) -> PromptReorderChipGeometry | None:
        """Return placement-owned landing geometry from the presenter."""

        result = self._landing_shadow.placement_owned_landing_geometry(
            self._landing_shadow_request(),
            reason=reason,
        )
        self._active_placement = result.active_placement
        self._geometry.active_placement = self._active_placement
        return result.geometry

    def _pending_landing_shadow_rect(self, *, reason: str) -> QRectF | None:
        """Return provisional landing-shadow bounds from the presenter."""

        return self._landing_shadow.pending_landing_shadow_rect(
            self._landing_shadow_request(),
            reason=reason,
        )

    def _pending_shadow_preview_visual(
        self,
        *,
        reason: str,
    ) -> PromptChipVisual | None:
        """Return provisional landing-shadow visual from the presenter."""

        return self._landing_shadow.pending_shadow_preview_visual(
            self._landing_shadow_request(),
            reason=reason,
        )

    def _landing_preview_for_active_target(self) -> PromptReorderChipGeometry | None:
        """Return active-target landing geometry from the presenter."""

        result = self._landing_shadow.landing_preview_for_active_target(
            self._landing_shadow_request()
        )
        self._active_placement = result.active_placement
        self._geometry.active_placement = self._active_placement
        return result.geometry

    def _insertion_marker_rect(self) -> QRectF | None:
        """Return the insertion marker rect for the current placeholder slot."""

        if (
            self._gesture.state.dragged_segment_index is None
            or self._gesture.state.active_drop_target is None
        ):
            self._log_interaction_event(
                "target_visual.marker_skipped",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                has_dragged_segment=self._gesture.state.dragged_segment_index
                is not None,
                has_active_target=self._gesture.state.active_drop_target is not None,
            )
            return None
        if self._landing_shadow.should_suppress_marker_for_landing_feedback(
            self._landing_shadow_request()
        ):
            return None
        for visual in self._drop_target_visuals:
            if visual.target != self._gesture.state.active_drop_target:
                continue
            marker_rect = QRectF(
                visual.hit_rect.center().x() - (_INSERTION_WIDTH / 2.0),
                visual.hit_rect.center().y() - (visual.hit_rect.height() / 2.0),
                _INSERTION_WIDTH,
                visual.hit_rect.height(),
            )
            self._log_interaction_event(
                "target_visual.marker_rect",
                gesture_id=self._instrumentation_gesture_id,
                event_id=self._instrumentation_event_id,
                **self._telemetry.target_context(
                    self._gesture.state.active_drop_target, prefix="active_target"
                ),
                **reorder_drag_rect_context(visual.hit_rect, prefix="target_hit"),
                **reorder_drag_rect_context(marker_rect, prefix="marker"),
            )
            self._instrumentation_marker_fallback_count += 1
            return marker_rect
        self._log_reorder_anomaly(
            "anomaly.active_target_without_visual",
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            **self._telemetry.target_context(
                self._gesture.state.active_drop_target, prefix="active_target"
            ),
        )
        return None

    def _ensure_drag_proxy_render_state(self) -> bool:
        """Apply rebuilt drag-proxy render state when render inputs require it."""

        if (
            self._gesture.state.dragged_segment_index is None
            or self._document_view is None
        ):
            return False
        started_at = reorder_drag_started_at()
        dragged_segment = self._segments_by_index[
            self._gesture.state.dragged_segment_index
        ]
        chip_state = prompt_reorder_chip_widget_state(
            self._gesture.state.dragged_segment_index,
            visual_style=self._visual_style,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            hovered_segment_index=self._gesture.state.hovered_segment_index,
            active_segment_index=self._gesture.state.active_segment_index,
            pressed_segment_index=self._gesture.state.pressed_segment_index,
        )
        sync = self._drag_proxy_state_factory.ensure_render_state(
            PromptReorderDragProxyRenderInputs(
                segment_index=dragged_segment.index,
                segment_text=dragged_segment.serialized_text,
                source_revision=self._source_revision,
                fill_color=chip_state.style.fill_color,
                border_color=chip_state.style.border_color,
                font=self._drag_proxy.font(),
                palette=self._drag_proxy.palette(),
            )
        )
        if not sync.rebuilt:
            return False
        self._drag_proxy.set_render_state(sync.render_state)
        self._log_interaction_timing(
            "drag_proxy.sync_segment",
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            dragged_segment_index=self._gesture.state.dragged_segment_index,
            segment_text_length=len(dragged_segment.serialized_text),
            proxy_width=self._drag_proxy.width(),
            proxy_height=self._drag_proxy.height(),
        )
        return True

    def _drag_landing_geometry(self) -> PromptReorderChipGeometry | None:
        """Return the current dragged segment's destination geometry when it exists."""

        if self._gesture.state.dragged_segment_index is None:
            return None
        return self._preview_chip_geometry_for_segment(
            self._gesture.state.dragged_segment_index
        )

    def _move_drag_proxy(self, global_pos: QPoint, *, log_timing: bool = True) -> float:
        """Move the floating drag proxy near the pointer."""

        started_at = reorder_drag_started_at()
        proxy_size = self._drag_proxy.size()
        if proxy_size.isEmpty():
            proxy_size = self._drag_proxy.sizeHint()
        pointer_pos = self._drag_proxy_host.mapFromGlobal(global_pos)
        editor_rect_in_host = map_rect_to_host(
            self._editor.viewport(),
            self._editor.viewport().rect(),
            self._drag_proxy_host,
        )
        placement_context = PromptReorderDragProxyPlacementContext(
            pointer_global_position=global_pos,
            pointer_host_position=pointer_pos,
            proxy_size=proxy_size,
            editor_rect_in_host=editor_rect_in_host,
            host_rect=self._drag_proxy_host.rect(),
        )
        proxy_rect = self._drag_proxy_placement.proxy_rect_for_pointer(
            placement_context
        )
        self._drag_proxy.setGeometry(proxy_rect)
        self._drag_proxy.raise_()
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        if not log_timing:
            return elapsed_ms
        return self._log_interaction_timing(
            "drag_proxy.move",
            started_at=started_at,
            gesture_id=self._instrumentation_gesture_id,
            event_id=self._instrumentation_event_id,
            proxy_width=proxy_rect.width(),
            proxy_height=proxy_rect.height(),
            proxy_left=proxy_rect.left(),
            proxy_top=proxy_rect.top(),
        )
