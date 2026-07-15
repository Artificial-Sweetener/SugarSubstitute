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

"""Own prompt reorder interaction layout, placement, and preview geometry state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptGapBlankLineDropTarget,
    PromptLineDropTarget,
    PromptReorderDropTarget,
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
from .reorder_chip_geometry import PromptReorderChipGeometrySnapshot
from .reorder_drop_targets import (
    PromptReorderBlankLineDropLane,
    PromptReorderDropLane,
    PromptReorderDropTargetVisual,
    PromptReorderRowDropLane,
)
from .reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationInput,
    PromptReorderKeyboardNavigationResult,
    PromptReorderKeyboardNavigator,
    PromptReorderLayoutPolicy,
)
from .reorder_placement_geometry import (
    PromptReorderPlacementGeometry,
    PromptReorderPlacementSnapshot,
)
from .reorder_state import (
    PromptReorderGeometryGenerationState,
    PromptReorderPreparedGeometryIdentity,
    PromptReorderPreviewTargetIdentity,
    PromptReorderPreviewTargetState,
    ReorderBaseDragGeometryKey,
    ReorderLayoutViewKey,
    ReorderPreviewSnapshotKey,
    ReorderSourceFingerprint,
    reorder_base_drag_geometry_key,
    reorder_source_fingerprint,
)


class PromptReorderGeometryHost(Protocol):
    """Describe projection geometry APIs used by the reorder geometry owner."""

    def reorder_preview_chip_geometry_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned preview reorder chip geometry."""

    def reorder_base_drag_chip_geometry_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return projection-owned base-drag reorder chip geometry."""

    def reorder_base_drag_placement_snapshot(
        self,
        *,
        snapshot: PromptReorderPreviewSnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Return projection-owned base-drag placement geometry."""


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryRefresh:
    """Carry projection snapshot changes produced by one geometry refresh."""

    previous_preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    previous_base_drag_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    base_drag_chip_snapshot: PromptReorderChipGeometrySnapshot | None
    placement_snapshot: PromptReorderPlacementSnapshot | None
    drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...]
    drop_target_lanes: tuple[PromptReorderDropLane, ...]
    preview_geometry_identity: PromptReorderPreviewTargetIdentity | None
    base_drag_geometry_reused: bool
    base_drag_geometry_rebuilt: bool


class PromptReorderInteractionGeometry:
    """Coordinate reorder layout, placement, lane, and preview identity state."""

    def __init__(
        self,
        *,
        layout_policy: PromptReorderLayoutPolicy,
        geometry_host: PromptReorderGeometryHost,
    ) -> None:
        """Store projection collaborators without depending on overlay widgets."""

        self._layout_policy = layout_policy
        self._geometry_host = geometry_host
        self._keyboard_navigator = PromptReorderKeyboardNavigator(
            layout_policy=layout_policy
        )
        self.document_view: PromptDocumentView | None = None
        self.original_layout_view: PromptReorderLayoutView | None = None
        self.current_layout_view: PromptReorderLayoutView | None = None
        self.base_drag_layout_view: PromptReorderLayoutView | None = None
        self.preview_layout_view: PromptReorderLayoutView | None = None
        self.original_reorder_state: PromptReorderStateView | None = None
        self.current_reorder_state: PromptReorderStateView | None = None
        self.base_drag_reorder_state: PromptReorderStateView | None = None
        self.preview_reorder_state: PromptReorderStateView | None = None
        self.preview_snapshot: PromptReorderPreviewSnapshot | None = None
        self.base_drag_snapshot: PromptReorderPreviewSnapshot | None = None
        self.preview_layout_target_identity: (
            PromptReorderPreviewTargetIdentity | None
        ) = None
        self.preview_geometry_target_identity: (
            PromptReorderPreviewTargetIdentity | None
        ) = None
        self.live_chip_geometry_snapshot: PromptReorderChipGeometrySnapshot | None = (
            None
        )
        self.preview_chip_geometry_snapshot: (
            PromptReorderChipGeometrySnapshot | None
        ) = None
        self.base_drag_chip_geometry_snapshot: (
            PromptReorderChipGeometrySnapshot | None
        ) = None
        self.placement_snapshot: PromptReorderPlacementSnapshot | None = None
        self.active_placement: PromptReorderPlacementGeometry | None = None
        self.drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...] = ()
        self.drop_target_lanes: tuple[PromptReorderDropLane, ...] = ()
        self.initial_ordered_indices: tuple[int, ...] = ()
        self.ordered_segment_indices: list[int] = []
        self.last_base_drag_geometry_key: ReorderBaseDragGeometryKey | None = None
        self._last_viewport_identity: object | None = None

    def set_session(
        self,
        document_view: PromptDocumentView,
        layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        ordered_indices: tuple[int, ...],
    ) -> None:
        """Replace all source/layout state for a reorder overlay session."""

        self.document_view = document_view
        self.original_layout_view = layout_view
        self.current_layout_view = layout_view
        self.base_drag_layout_view = None
        self.preview_layout_view = None
        self.original_reorder_state = reorder_state
        self.current_reorder_state = reorder_state
        self.base_drag_reorder_state = None
        self.preview_reorder_state = None
        self.clear_preview_target_identity()
        self.preview_snapshot = None
        self.base_drag_snapshot = None
        self.live_chip_geometry_snapshot = None
        self.preview_chip_geometry_snapshot = None
        self.base_drag_chip_geometry_snapshot = None
        self.placement_snapshot = None
        self.active_placement = None
        self.drop_target_visuals = ()
        self.drop_target_lanes = ()
        self.initial_ordered_indices = ordered_indices
        self.ordered_segment_indices = list(ordered_indices)
        self.last_base_drag_geometry_key = None

    def clear_drag_context(self) -> None:
        """Clear base-drag, placement, and preview geometry for one drag lifecycle."""

        self.base_drag_layout_view = None
        self.base_drag_reorder_state = None
        self.base_drag_chip_geometry_snapshot = None
        self.base_drag_snapshot = None
        self.preview_layout_view = None
        self.preview_reorder_state = None
        self.preview_chip_geometry_snapshot = None
        self.placement_snapshot = None
        self.active_placement = None
        self.drop_target_visuals = ()
        self.drop_target_lanes = ()
        self.last_base_drag_geometry_key = None
        self.clear_preview_target_identity()

    def clear_preview_target_identity(self) -> None:
        """Clear target identity for preview layout and geometry snapshots."""

        self.preview_layout_target_identity = None
        self.preview_geometry_target_identity = None

    def begin_drag(
        self,
        *,
        dragged_segment_index: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderLayoutView | None:
        """Build and store the base-drag layout for one pointer gesture."""

        if (
            self.document_view is None
            or self.current_layout_view is None
            or self.current_reorder_state is None
        ):
            return None
        started_at = reorder_drag_started_at()
        self.base_drag_reorder_state = (
            self._layout_policy.build_base_drag_reorder_state_from_state(
                self.current_reorder_state,
                dragged_segment_index=dragged_segment_index,
            )
        )
        self.base_drag_layout_view = (
            self._layout_policy.build_base_drag_layout_view_from_layout(
                self.document_view,
                self.current_layout_view,
                dragged_segment_index=dragged_segment_index,
            )
        )
        self.preview_layout_view = None
        self.preview_reorder_state = None
        self.clear_preview_target_identity()
        self.placement_snapshot = None
        self.active_placement = None
        self.last_base_drag_geometry_key = None
        log_reorder_drag_timing(
            "start.base_drag_layout",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_count=len(self.base_drag_layout_view.rows),
            gap_count=len(self.base_drag_layout_view.gaps),
        )
        return self.base_drag_layout_view

    def ensure_keyboard_context(
        self,
        *,
        active_segment_index: int,
        base_drag_segment_index: int | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Prepare stable base-drag geometry for keyboard reorder navigation."""

        if (
            self.document_view is None
            or self.current_layout_view is None
            or self.current_reorder_state is None
        ):
            return False
        if (
            base_drag_segment_index == active_segment_index
            and self.base_drag_layout_view is not None
            and self.drop_target_lanes
        ):
            return True
        started_at = reorder_drag_started_at()
        self.base_drag_reorder_state = (
            self._layout_policy.build_base_drag_reorder_state_from_state(
                self.current_reorder_state,
                dragged_segment_index=active_segment_index,
            )
        )
        self.base_drag_layout_view = (
            self._layout_policy.build_base_drag_layout_view_from_layout(
                self.document_view,
                self.current_layout_view,
                dragged_segment_index=active_segment_index,
            )
        )
        self.preview_layout_view = None
        self.preview_reorder_state = None
        self.clear_preview_target_identity()
        log_reorder_drag_timing(
            "start.base_drag_layout",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            row_count=len(self.base_drag_layout_view.rows),
            gap_count=len(self.base_drag_layout_view.gaps),
        )
        return bool(self.drop_target_lanes)

    def update_preview_layout(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Refresh the typed reorder preview layout for active drag state."""

        total_started_at = reorder_drag_started_at()
        built_preview_layout = False
        if self.document_view is None:
            return False

        if dragged_segment_index is not None and self.base_drag_layout_view is not None:
            current_layout_view = self.current_layout_view
            current_reorder_state = self.current_reorder_state
            if current_layout_view is None or current_reorder_state is None:
                return False
            if active_target is not None:
                started_at = reorder_drag_started_at()
                self.preview_layout_target_identity = (
                    self.preview_target_identity_for_target(
                        dragged_segment_index=dragged_segment_index,
                        target=active_target,
                        viewport_identity=viewport_identity,
                    )
                )
                self.preview_layout_view = (
                    self._layout_policy.build_preview_drop_layout_view_from_layout(
                        self.document_view,
                        current_layout_view,
                        dragged_segment_index=dragged_segment_index,
                        drop_target=active_target,
                    )
                )
                self.preview_reorder_state = (
                    self._layout_policy.build_preview_drop_reorder_state_from_state(
                        self.document_view,
                        current_reorder_state,
                        current_layout_view=current_layout_view,
                        base_drag_layout_view=self.base_drag_layout_view,
                        dragged_segment_index=dragged_segment_index,
                        drop_target=active_target,
                    )
                )
                built_preview_layout = True
                log_reorder_drag_timing(
                    "preview_layout.build_drop_layout",
                    started_at=started_at,
                    gesture_id=gesture_id,
                    event_id=event_id,
                    dragged_segment_index=dragged_segment_index,
                    target_kind=reorder_drag_target_kind(active_target),
                    row_count=len(self.preview_layout_view.rows),
                    gap_count=len(self.preview_layout_view.gaps),
                )
            else:
                self.preview_layout_view = self.base_drag_layout_view
                self.preview_reorder_state = self.base_drag_reorder_state
                self.preview_layout_target_identity = None

        preview_layout = self.layout_for_painted_preview(
            dragged_segment_index=dragged_segment_index
        )
        if preview_layout is None:
            self.preview_layout_target_identity = None
            self.ordered_segment_indices = list(self.initial_ordered_indices)
            self.preview_reorder_state = None
            log_reorder_drag_timing(
                "preview_layout.total",
                started_at=total_started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                dragged_segment_index=dragged_segment_index,
                target_kind=reorder_drag_target_kind(active_target),
                built_preview_layout=built_preview_layout,
                preview_active=False,
                ordered_count=len(self.ordered_segment_indices),
            )
            return built_preview_layout

        started_at = reorder_drag_started_at()
        self.ordered_segment_indices = list(
            self._layout_policy.reorder_layout_chip_indices(preview_layout)
        )
        order_elapsed_ms = log_reorder_drag_timing(
            "preview_layout.order_indices",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            ordered_count=len(self.ordered_segment_indices),
        )
        log_reorder_drag_timing(
            "preview_layout.total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=dragged_segment_index,
            target_kind=reorder_drag_target_kind(active_target),
            built_preview_layout=built_preview_layout,
            preview_active=True,
            row_count=len(preview_layout.rows),
            gap_count=len(preview_layout.gaps),
            ordered_count=len(self.ordered_segment_indices),
            order_elapsed_ms=f"{order_elapsed_ms:.3f}",
        )
        return built_preview_layout

    def set_preview_snapshots(
        self,
        snapshot: PromptReorderPreviewSnapshot | None,
        *,
        base_drag_snapshot: PromptReorderPreviewSnapshot | None,
        ordered_chip_indices: tuple[int, ...],
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
    ) -> None:
        """Store controller-built preview snapshots with stale-safe identity."""

        self.preview_snapshot = snapshot
        self.base_drag_snapshot = base_drag_snapshot
        if snapshot is not None:
            self.ordered_segment_indices = list(ordered_chip_indices)
            self.preview_layout_target_identity = (
                self.preview_target_identity_for_target(
                    dragged_segment_index=dragged_segment_index,
                    target=active_target,
                    viewport_identity=viewport_identity,
                )
            )
        else:
            self.preview_geometry_target_identity = None

    def refresh_preview_geometry(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderGeometryRefresh:
        """Refresh preview/base chip snapshots and prepared placement lanes."""

        self._last_viewport_identity = viewport_identity
        previous_preview_chip_snapshot = self.preview_chip_geometry_snapshot
        previous_base_drag_chip_snapshot = self.base_drag_chip_geometry_snapshot
        next_preview_chip_snapshot: PromptReorderChipGeometrySnapshot | None = None
        next_preview_geometry_identity: PromptReorderPreviewTargetIdentity | None = None
        preview_layout = self.layout_for_painted_preview(
            dragged_segment_index=dragged_segment_index
        )
        if self.preview_snapshot is not None and preview_layout is not None:
            next_preview_chip_snapshot = (
                self._geometry_host.reorder_preview_chip_geometry_snapshot(
                    snapshot=self.preview_snapshot,
                    layout_view=preview_layout,
                )
            )
            next_preview_geometry_identity = (
                self.preview_layout_target_identity
                if self.preview_layout_target_identity is not None
                else self.preview_target_identity_for_target(
                    dragged_segment_index=dragged_segment_index,
                    target=active_target,
                    viewport_identity=viewport_identity,
                )
            )

        next_base_drag_chip_snapshot: PromptReorderChipGeometrySnapshot | None = None
        next_placement_snapshot: PromptReorderPlacementSnapshot | None = None
        next_drop_target_visuals: tuple[PromptReorderDropTargetVisual, ...] = ()
        next_drop_target_lanes: tuple[PromptReorderDropLane, ...] = ()
        base_drag_geometry_reused = False
        base_drag_geometry_rebuilt = False
        base_geometry_key = self.base_drag_geometry_key(
            viewport_identity=viewport_identity,
            dragged_segment_index=dragged_segment_index,
        )
        if (
            base_geometry_key is not None
            and base_geometry_key == self.last_base_drag_geometry_key
            and self.base_drag_chip_geometry_snapshot is not None
            and self.placement_snapshot is not None
        ):
            base_drag_geometry_reused = True
            next_base_drag_chip_snapshot = self.base_drag_chip_geometry_snapshot
            next_placement_snapshot = self.placement_snapshot
            next_drop_target_visuals = self.drop_target_visuals
            next_drop_target_lanes = self.drop_target_lanes
            log_reorder_drag_event(
                "preview_geometry.base_drag_reused",
                gesture_id=gesture_id,
                event_id=event_id,
                base_visual_count=len(
                    next_base_drag_chip_snapshot.geometries_by_chip_index
                ),
                placement_count=len(next_placement_snapshot.placements),
                lane_count=len(next_drop_target_lanes),
                key_changed=False,
            )
        elif (
            self.base_drag_layout_view is not None
            and self.base_drag_snapshot is not None
        ):
            next_base_drag_chip_snapshot = (
                self._geometry_host.reorder_base_drag_chip_geometry_snapshot(
                    snapshot=self.base_drag_snapshot,
                    layout_view=self.base_drag_layout_view,
                )
            )
            next_placement_snapshot = (
                self._geometry_host.reorder_base_drag_placement_snapshot(
                    snapshot=self.base_drag_snapshot,
                    layout_view=self.base_drag_layout_view,
                )
            )
            (
                next_drop_target_visuals,
                next_drop_target_lanes,
            ) = self.drop_geometry_from_placements(
                next_placement_snapshot,
                gesture_id=gesture_id,
                event_id=event_id,
            )
            self.last_base_drag_geometry_key = base_geometry_key
            base_drag_geometry_rebuilt = True
            log_reorder_drag_event(
                "preview_geometry.base_drag_rebuilt",
                gesture_id=gesture_id,
                event_id=event_id,
                base_visual_count=len(
                    next_base_drag_chip_snapshot.geometries_by_chip_index
                ),
                placement_count=len(next_placement_snapshot.placements),
                lane_count=len(next_drop_target_lanes),
                key_changed=True,
            )
        else:
            self.last_base_drag_geometry_key = None

        self.preview_chip_geometry_snapshot = next_preview_chip_snapshot
        self.preview_geometry_target_identity = next_preview_geometry_identity
        self.base_drag_chip_geometry_snapshot = next_base_drag_chip_snapshot
        self.placement_snapshot = next_placement_snapshot
        self.drop_target_visuals = next_drop_target_visuals
        self.drop_target_lanes = next_drop_target_lanes
        return PromptReorderGeometryRefresh(
            previous_preview_chip_snapshot=previous_preview_chip_snapshot,
            previous_base_drag_chip_snapshot=previous_base_drag_chip_snapshot,
            preview_chip_snapshot=next_preview_chip_snapshot,
            base_drag_chip_snapshot=next_base_drag_chip_snapshot,
            placement_snapshot=next_placement_snapshot,
            drop_target_visuals=next_drop_target_visuals,
            drop_target_lanes=next_drop_target_lanes,
            preview_geometry_identity=next_preview_geometry_identity,
            base_drag_geometry_reused=base_drag_geometry_reused,
            base_drag_geometry_rebuilt=base_drag_geometry_rebuilt,
        )

    def apply_keyboard_drop_target(
        self,
        drop_target: PromptReorderDropTarget,
        *,
        active_segment_index: int | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Commit one keyboard-selected target into current preview state."""

        result = self._keyboard_navigator.apply_keyboard_drop_target(
            self._keyboard_navigation_input(
                active_segment_index=active_segment_index,
                active_target=drop_target,
                preferred_x=None,
            ),
            drop_target,
        )
        if not self._apply_keyboard_navigation_result(
            result,
            active_segment_index=active_segment_index,
        ):
            return False

        log_reorder_drag_event(
            "drop_target.changed_rebuild_path",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=active_segment_index,
            target_kind=reorder_drag_target_kind(drop_target),
            ordered_count=len(self.ordered_segment_indices),
        )
        return True

    def move_keyboard_horizontally(
        self,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        preferred_x: float | None,
        step: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderKeyboardNavigationResult:
        """Apply one horizontal keyboard move through projection navigation."""

        result = self._keyboard_navigator.move_horizontally(
            self._keyboard_navigation_input(
                active_segment_index=active_segment_index,
                active_target=active_target,
                preferred_x=preferred_x,
            ),
            step=step,
        )
        self._apply_logged_keyboard_navigation_result(
            result,
            active_segment_index=active_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return result

    def move_keyboard_vertically(
        self,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        direction: int,
        preferred_x: float | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderKeyboardNavigationResult:
        """Apply one vertical keyboard move through projection navigation."""

        result = self._keyboard_navigator.move_vertically(
            self._keyboard_navigation_input(
                active_segment_index=active_segment_index,
                active_target=active_target,
                preferred_x=preferred_x,
            ),
            direction=direction,
        )
        self._apply_logged_keyboard_navigation_result(
            result,
            active_segment_index=active_segment_index,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        return result

    def current_effective_drop_target(
        self,
        *,
        active_target: PromptReorderDropTarget | None,
        active_segment_index: int | None,
    ) -> PromptReorderDropTarget | None:
        """Return the current insertion target relative to base-drag state."""

        return self._keyboard_navigator.current_effective_drop_target(
            self._keyboard_navigation_input(
                active_segment_index=active_segment_index,
                active_target=active_target,
                preferred_x=None,
            )
        )

    def resolve_drop_target_for_current_layout(
        self,
        *,
        active_segment_index: int | None,
    ) -> PromptReorderDropTarget | None:
        """Resolve the target whose preview layout matches the current order."""

        return self._keyboard_navigator.resolve_drop_target_for_current_layout(
            self._keyboard_navigation_input(
                active_segment_index=active_segment_index,
                active_target=None,
                preferred_x=None,
            )
        )

    def all_visible_drop_targets(self) -> tuple[PromptReorderDropTarget, ...]:
        """Return every visible row-slot and blank-line target in stable order."""

        return self._keyboard_navigator.all_visible_drop_targets(self.drop_target_lanes)

    def row_slot_targets_in_reading_order(self) -> tuple[PromptLineDropTarget, ...]:
        """Return visible populated-row insertion targets in reading order."""

        return self._keyboard_navigator.row_slot_targets_in_reading_order(
            self.drop_target_lanes
        )

    def lane_index_for_target(self, target: PromptReorderDropTarget) -> int | None:
        """Return the visible lane index that owns the supplied target."""

        return self._keyboard_navigator.lane_index_for_target(
            target,
            self.drop_target_lanes,
        )

    def target_for_lane(
        self,
        lane: PromptReorderDropLane,
        *,
        preferred_x: float,
    ) -> PromptReorderDropTarget | None:
        """Resolve one lane-local drop target for keyboard vertical movement."""

        return self._keyboard_navigator.target_for_lane(
            lane,
            preferred_x=preferred_x,
        )

    @staticmethod
    def edge_target_for_lane(
        lane: PromptReorderDropLane,
        *,
        direction: int,
    ) -> PromptReorderDropTarget | None:
        """Resolve the edge-clamp destination when no further lane exists."""

        return PromptReorderKeyboardNavigator.edge_target_for_lane(
            lane,
            direction=direction,
        )

    def row_slot_target_nearest_x(
        self,
        lane: PromptReorderRowDropLane,
        *,
        preferred_x: float,
    ) -> PromptLineDropTarget | None:
        """Return the populated-row slot whose center is nearest preferred x."""

        return PromptReorderKeyboardNavigator.row_slot_target_nearest_x(
            lane,
            preferred_x=preferred_x,
        )

    def target_center_x(self, target: PromptReorderDropTarget) -> float:
        """Return the horizontal center used to preserve keyboard lane intent."""

        return PromptReorderKeyboardNavigator.target_center_x(
            target,
            self.drop_target_lanes,
        )

    def _keyboard_navigation_input(
        self,
        *,
        active_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        preferred_x: float | None,
    ) -> PromptReorderKeyboardNavigationInput:
        """Return prepared state consumed by the keyboard navigator."""

        active_segment_center: tuple[float, float] | None = None
        if (
            active_segment_index is not None
            and self.live_chip_geometry_snapshot is not None
        ):
            active_geometry = (
                self.live_chip_geometry_snapshot.geometries_by_chip_index.get(
                    active_segment_index
                )
            )
            if active_geometry is not None:
                center = active_geometry.hotspot_rect.center()
                active_segment_center = (center.x(), center.y())
        return PromptReorderKeyboardNavigationInput(
            document_view=self.document_view,
            current_layout_view=self.current_layout_view,
            active_segment_index=active_segment_index,
            active_target=active_target,
            preferred_x=preferred_x,
            drop_target_lanes=self.drop_target_lanes,
            active_segment_center=active_segment_center,
        )

    def _apply_keyboard_navigation_result(
        self,
        result: PromptReorderKeyboardNavigationResult,
        *,
        active_segment_index: int | None,
    ) -> bool:
        """Apply a navigator result to projection-owned session geometry."""

        if (
            not result.moved
            or result.proposed_layout_view is None
            or result.proposed_base_drag_layout_view is None
        ):
            return False
        if (
            self.document_view is None
            or self.current_layout_view is None
            or self.current_reorder_state is None
            or result.destination_target is None
            or active_segment_index is None
        ):
            return False
        proposed_reorder_state = (
            self._layout_policy.build_preview_drop_reorder_state_from_state(
                self.document_view,
                self.current_reorder_state,
                current_layout_view=self.current_layout_view,
                base_drag_layout_view=self.base_drag_layout_view,
                dragged_segment_index=active_segment_index,
                drop_target=result.destination_target,
            )
        )
        if (
            tuple(result.ordered_segment_indices) == self.initial_ordered_indices
            and result.proposed_layout_view == self.original_layout_view
            and self.original_layout_view is not None
            and self.original_reorder_state is not None
        ):
            proposed_layout_view = self.original_layout_view
            proposed_reorder_state = self.original_reorder_state
        else:
            proposed_layout_view = result.proposed_layout_view
        self.current_reorder_state = proposed_reorder_state
        self.base_drag_reorder_state = (
            self._layout_policy.build_base_drag_reorder_state_from_state(
                proposed_reorder_state,
                dragged_segment_index=active_segment_index,
            )
        )
        self.current_layout_view = proposed_layout_view
        self.preview_layout_view = None
        self.preview_reorder_state = None
        self.ordered_segment_indices = list(
            self._layout_policy.reorder_layout_chip_indices(proposed_layout_view)
        )
        self.base_drag_layout_view = (
            self._layout_policy.build_base_drag_layout_view_from_layout(
                self.document_view,
                proposed_layout_view,
                dragged_segment_index=active_segment_index,
            )
        )
        self.clear_preview_target_identity()
        return True

    def _apply_logged_keyboard_navigation_result(
        self,
        result: PromptReorderKeyboardNavigationResult,
        *,
        active_segment_index: int | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> bool:
        """Apply a keyboard move result and record prompt-safe structural context."""

        if not self._apply_keyboard_navigation_result(
            result,
            active_segment_index=active_segment_index,
        ):
            return False
        log_reorder_drag_event(
            "drop_target.changed_rebuild_path",
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=active_segment_index,
            target_kind=reorder_drag_target_kind(result.destination_target),
            ordered_count=len(self.ordered_segment_indices),
        )
        return True

    def drop_geometry_from_placements(
        self,
        snapshot: PromptReorderPlacementSnapshot,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> tuple[
        tuple[PromptReorderDropTargetVisual, ...], tuple[PromptReorderDropLane, ...]
    ]:
        """Expose placement geometry as prepared target visuals and lanes."""

        visual_targets = tuple(
            PromptReorderDropTargetVisual(placement.target, placement.hit_rect)
            for placement in snapshot.placements
        )
        row_groups: dict[tuple[int, int], list[PromptReorderPlacementGeometry]] = {}
        blank_lanes: list[PromptReorderBlankLineDropLane] = []
        for placement in snapshot.placements:
            if isinstance(placement.target, PromptGapBlankLineDropTarget):
                blank_lanes.append(
                    PromptReorderBlankLineDropLane(
                        target=placement.target,
                        hit_rect=placement.hit_rect,
                    )
                )
                continue
            if isinstance(placement.target, PromptLineDropTarget):
                row_groups.setdefault(
                    (
                        placement.target.row_index,
                        placement.placement_id.visual_line_index,
                    ),
                    [],
                ).append(placement)

        row_lanes: list[PromptReorderRowDropLane] = []
        for (row_index, visual_row_index), placements in sorted(row_groups.items()):
            placements.sort(
                key=lambda placement: (
                    cast(PromptLineDropTarget, placement.target).insertion_index
                )
            )
            lane_rect = QRectF(placements[0].visual_line_rect)
            slot_visuals = tuple(
                PromptReorderDropTargetVisual(placement.target, placement.hit_rect)
                for placement in placements
            )
            row_lanes.append(
                PromptReorderRowDropLane(
                    row_index=row_index,
                    visual_row_index=visual_row_index,
                    hit_rect=lane_rect,
                    slot_visuals=slot_visuals,
                )
            )

        lanes: list[PromptReorderDropLane] = [*row_lanes, *blank_lanes]
        lanes.sort(key=lambda lane: lane.hit_rect.center().y())
        log_reorder_drag_event(
            "placement_geometry.snapshot",
            gesture_id=gesture_id,
            event_id=event_id,
            placement_count=len(snapshot.placements),
            row_lane_count=len(row_lanes),
            blank_lane_count=len(blank_lanes),
            visual_line_count=snapshot.visual_line_count,
            layout_width=f"{snapshot.layout_width:.2f}",
            content_height=f"{snapshot.content_height:.2f}",
        )
        return visual_targets, tuple(lanes)

    def layout_for_painted_preview(
        self,
        *,
        dragged_segment_index: int | None,
    ) -> PromptReorderLayoutView | None:
        """Return the layout represented by active preview geometry."""

        if dragged_segment_index is not None:
            return self.preview_layout_view
        if self.current_reorder_state != self.original_reorder_state:
            return self.current_layout_view
        return None

    def preview_target_identity_for_target(
        self,
        *,
        dragged_segment_index: int | None,
        target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
    ) -> PromptReorderPreviewTargetIdentity | None:
        """Return the preview identity expected for one semantic target."""

        if dragged_segment_index is None or target is None:
            return None
        return PromptReorderPreviewTargetIdentity(
            source_fingerprint=self.source_fingerprint,
            projection_identity=layout_view_key(self.current_layout_view),
            dragged_segment_index=dragged_segment_index,
            target=target,
            preview_layout_key=layout_view_key(self.preview_layout_view),
            base_drag_layout_key=layout_view_key(self.base_drag_layout_view),
            viewport_identity=viewport_identity,
        )

    def preview_geometry_matches_target(
        self,
        *,
        dragged_segment_index: int | None,
        target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
    ) -> bool:
        """Return whether published preview geometry belongs to the active target."""

        expected_identity = self.preview_target_identity_for_target(
            dragged_segment_index=dragged_segment_index,
            target=target,
            viewport_identity=viewport_identity,
        )
        return (
            expected_identity is not None
            and self.preview_geometry_target_identity == expected_identity
        )

    def preview_target_identity_context(
        self,
        identity: PromptReorderPreviewTargetIdentity | None,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """Return structured fields for one preview target identity."""

        if identity is None:
            return {
                f"{prefix}_dragged_segment_index": None,
                f"{prefix}_target_kind": "none",
                f"{prefix}_source_layout_key": "none",
            }
        return {
            f"{prefix}_dragged_segment_index": identity.dragged_segment_index,
            f"{prefix}_target_kind": reorder_drag_target_kind(identity.target),
            f"{prefix}_source_layout_key": repr(identity.source_fingerprint),
            f"{prefix}_preview_layout_key": repr(identity.preview_layout_key),
            f"{prefix}_base_drag_layout_key": repr(identity.base_drag_layout_key),
            f"{prefix}_viewport_identity": repr(identity.viewport_identity),
        }

    def prepared_geometry_identity(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
    ) -> PromptReorderPreparedGeometryIdentity:
        """Return the full prepared-geometry identity for stale-safe refresh."""

        return PromptReorderPreparedGeometryIdentity(
            source_fingerprint=self.source_fingerprint,
            projection_identity=layout_view_key(self.current_layout_view),
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            preview_layout_key=layout_view_key(self.preview_layout_view),
            base_drag_layout_key=layout_view_key(self.base_drag_layout_view),
            preview_snapshot_key=preview_snapshot_key(self.preview_snapshot),
            base_drag_snapshot_key=preview_snapshot_key(self.base_drag_snapshot),
            viewport_identity=viewport_identity,
        )

    def preview_target_state(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
    ) -> PromptReorderPreviewTargetState:
        """Return display-only preview target state owned by projection geometry."""

        return PromptReorderPreviewTargetState(
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            ordered_segment_indices=tuple(self.ordered_segment_indices),
            preview_layout_target_identity=self.preview_layout_target_identity,
            preview_geometry_target_identity=self.preview_geometry_target_identity,
            has_preview_layout=self.preview_layout_view is not None,
            has_base_drag_layout=self.base_drag_layout_view is not None,
        )

    def geometry_generation_state(
        self,
        *,
        generation_id: int,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object,
    ) -> PromptReorderGeometryGenerationState:
        """Return the prepared-geometry generation visible to non-widget readers."""

        return PromptReorderGeometryGenerationState(
            generation_id=generation_id,
            prepared_geometry_identity=self.prepared_geometry_identity(
                dragged_segment_index=dragged_segment_index,
                active_target=active_target,
                viewport_identity=viewport_identity,
            ),
            base_drag_geometry_key=self.base_drag_geometry_key(
                viewport_identity=viewport_identity,
                dragged_segment_index=dragged_segment_index,
            ),
        )

    def base_drag_geometry_key(
        self,
        *,
        viewport_identity: object,
        dragged_segment_index: int | None,
    ) -> ReorderBaseDragGeometryKey | None:
        """Return the identity for reusable stable base-drag geometry."""

        if self.base_drag_layout_view is None or self.base_drag_snapshot is None:
            return None
        return reorder_base_drag_geometry_key(
            base_drag_layout_key=layout_view_key(self.base_drag_layout_view),
            base_drag_snapshot_key=preview_snapshot_key(self.base_drag_snapshot),
            viewport_identity=viewport_identity,
            dragged_segment_index=dragged_segment_index,
        )

    def ordered_indices_for_layout(
        self,
        layout_view: PromptReorderLayoutView | None,
    ) -> tuple[int, ...]:
        """Return the chip order for one prepared layout view."""

        if layout_view is None:
            return ()
        return self._layout_policy.reorder_layout_chip_indices(layout_view)

    @property
    def source_fingerprint(self) -> ReorderSourceFingerprint:
        """Return a prompt-safe source identity for prepared geometry."""

        if self.document_view is None:
            return reorder_source_fingerprint("")
        return reorder_source_fingerprint(self.document_view.source_text)


def layout_view_key(
    layout_view: PromptReorderLayoutView | None,
) -> ReorderLayoutViewKey | None:
    """Return a prompt-safe key for one reorder layout view."""

    if layout_view is None:
        return None
    return (
        tuple((row.row_index, tuple(row.chip_indices)) for row in layout_view.rows),
        tuple(
            (
                gap.gap_index,
                gap.separator_text,
                gap.blank_line_count,
                gap.placement.value,
            )
            for gap in layout_view.gaps
        ),
    )


def preview_snapshot_key(
    snapshot: PromptReorderPreviewSnapshot | None,
) -> ReorderPreviewSnapshotKey | None:
    """Return a prompt-safe key for one preview snapshot."""

    if snapshot is None:
        return None
    return (
        reorder_source_fingerprint(snapshot.text),
        tuple(
            sorted(
                (chip_index, start, end)
                for chip_index, (
                    start,
                    end,
                ) in snapshot.chip_rendered_ranges_by_index.items()
            )
        ),
        tuple(
            sorted(
                (gap_index, start, end)
                for gap_index, (start, end) in snapshot.gap_ranges_by_index.items()
            )
        ),
    )


__all__ = [
    "PromptReorderGeometryHost",
    "PromptReorderGeometryRefresh",
    "PromptReorderInteractionGeometry",
    "PromptReorderKeyboardNavigationResult",
    "PromptReorderLayoutPolicy",
    "layout_view_key",
    "preview_snapshot_key",
]
