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

"""Provide reorder overlay doubles for prompt interaction tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from substitute.application.prompt_editor.reorder.intents import (
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderKeyboardMoveIntent,
)
from substitute.application.prompt_editor.reorder.preview_sync import (
    PromptReorderPreviewSyncContext,
)
from substitute.application.prompt_editor.reorder.session import (
    PromptReorderCommitSnapshot,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.core.state.revisions import (
    PromptSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.interactions.reorder_overlay_port import (
    PromptReorderOverlayAssembly,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderDragIntent,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_build_facts import (
    PromptReorderPreviewBuildFacts,
)
from tests.presentation.editor.prompt_editor.interactions.support.timing import (
    SignalDouble,
)


def reorder_state_for_indices(
    ordered_indices: tuple[int, ...],
    *,
    separator: str = ", ",
) -> PromptReorderStateView:
    """Return a deterministic reorder state for controller tests."""

    return PromptReorderStateView(
        ordered_chip_indices=ordered_indices,
        separator_slots=tuple(separator for _ in ordered_indices[:-1]),
        has_trailing_comma=False,
    )


class OverlayDouble:
    """Provide the overlay API used by reorder interaction tests."""

    def __init__(
        self,
        ordered_indices: list[int] | None = None,
        *,
        active_segment_index: int | None = None,
        drop_target: object | None = None,
        dragged_segment_index: int | None = None,
        current_layout_view: PromptReorderLayoutView | None = None,
        base_drag_layout_view: PromptReorderLayoutView | None = None,
        has_base_drag_placement_geometry: bool = False,
        should_flush_initial_landing_shadow_sync: bool = False,
        has_reordered: bool = True,
    ) -> None:
        """Store committed ordering and overlay lifecycle calls."""

        self._ordered_indices = [] if ordered_indices is None else ordered_indices
        self._current_reorder_state = reorder_state_for_indices(
            tuple(self._ordered_indices)
        )
        self._active_segment_index = active_segment_index
        self._drop_target = drop_target
        self._dragged_segment_index = dragged_segment_index
        self._current_layout_view = current_layout_view
        self._preview_layout_view: PromptReorderLayoutView | None = None
        self._base_drag_layout_view = base_drag_layout_view
        self._has_base_drag_placement_geometry = has_base_drag_placement_geometry
        self._should_flush_initial_landing_shadow_sync = (
            should_flush_initial_landing_shadow_sync
        )
        self._has_reordered = has_reordered
        self.cancel_drag_calls = 0
        self.closed = 0
        self.deleted = 0
        self.refresh_geometry_calls = 0
        self.refresh_geometry_reasons: list[str] = []
        self.needs_position_refresh_result = True
        self.needs_position_refresh_calls: list[str] = []
        self.autoscroll_flush_calls: list[str] = []
        self.keyboard_move_calls: list[str] = []
        self.keyboard_move_results: dict[str, bool] = {}
        self.keyboard_move_snapshots: dict[str, PromptReorderCommitSnapshot] = {}
        self.previewLayoutChanged = SignalDouble()
        self.drag_handler: Callable[[PromptReorderDragIntent], None] | None = None
        self.commit_handler: Callable[[PromptReorderCommitIntent], None] | None = None
        self.cancel_handler: Callable[[PromptReorderCancelIntent], None] | None = None
        self.set_chips_calls: list[
            tuple[object, object, tuple[int, ...], int | None]
        ] = []
        self.preview_snapshot_calls: list[
            tuple[object | None, object | None, tuple[int, ...]]
        ] = []
        self.preview_fact_snapshot_calls = 0
        self.show_calls = 0

    def commit_snapshot(self) -> PromptReorderCommitSnapshot:
        """Return the prepared reorder snapshot used by command commit."""

        return PromptReorderCommitSnapshot(
            reorder_state=self._current_reorder_state,
            layout_view=self._current_layout_view,
            ordered_chip_indices=tuple(self._ordered_indices),
            active_segment_index=self._active_segment_index,
            dragged_segment_index=self._dragged_segment_index,
            has_reordered=self._has_reordered,
        )

    def snapshot(self) -> PromptReorderPreviewBuildFacts:
        """Return one coherent preview-build generation."""

        self.preview_fact_snapshot_calls += 1
        return PromptReorderPreviewBuildFacts(
            preview_layout_view=self._preview_layout_view,
            base_drag_layout_view=self._base_drag_layout_view,
            preview_reorder_state=None,
            base_drag_reorder_state=None,
            ordered_chip_indices=tuple(self._ordered_indices),
            dragged_segment_index=self._dragged_segment_index,
            drop_target=cast(Any, self._drop_target),
        )

    def set_chips(
        self,
        document_view: object,
        reorder_layout_view: PromptReorderLayoutView,
        reorder_state: PromptReorderStateView,
        *,
        chips: tuple[Any, ...],
        active_chip_index: int | None = None,
        source_identity: PromptSourceIdentity | None = None,
    ) -> None:
        """Record chip publication from reorder mode entry."""

        _ = source_identity
        chip_indices = tuple(segment.index for segment in chips)
        self._ordered_indices = list(chip_indices)
        self._current_layout_view = reorder_layout_view
        self._current_reorder_state = reorder_state
        self.set_chips_calls.append(
            (document_view, reorder_layout_view, chip_indices, active_chip_index)
        )

    def set_preview_snapshot(
        self,
        snapshot: object | None,
        *,
        base_drag_snapshot: object | None = None,
        ordered_chip_indices: tuple[int, ...],
    ) -> None:
        """Record preview snapshot pushes from the controller."""

        self.preview_snapshot_calls.append(
            (snapshot, base_drag_snapshot, ordered_chip_indices)
        )

    def flush_pending_autoscroll_invalidation(self, *, reason: str) -> bool:
        """Record coalesced autoscroll flush requests from preview sync."""

        self.autoscroll_flush_calls.append(reason)
        return False

    def cancel_drag(self) -> None:
        """Record drag-cancel requests."""

        self.cancel_drag_calls += 1

    def close(self) -> bool:
        """Record overlay close requests."""

        self.closed += 1
        return True

    def deleteLater(self) -> None:  # noqa: N802
        """Record deferred overlay deletion requests."""

        self.deleted += 1

    def set_drag_handler(
        self,
        handler: Callable[[PromptReorderDragIntent], None] | None,
    ) -> None:
        """Store the drag intent handler."""

        self.drag_handler = handler

    def set_commit_handler(
        self,
        handler: Callable[[PromptReorderCommitIntent], None] | None,
    ) -> None:
        """Store the commit intent handler."""

        self.commit_handler = handler

    def set_cancel_handler(
        self,
        handler: Callable[[PromptReorderCancelIntent], None] | None,
    ) -> None:
        """Store the cancel intent handler."""

        self.cancel_handler = handler

    def refresh_geometry(self, *, reason: str = "test") -> None:
        """Record overlay-local geometry refresh requests."""

        self.refresh_geometry_calls += 1
        self.refresh_geometry_reasons.append(reason)

    def needs_position_refresh(self, *, reason: str = "test") -> bool:
        """Return the configured position-refresh decision."""

        self.needs_position_refresh_calls.append(reason)
        return self.needs_position_refresh_result

    def show(self) -> None:
        """Record overlay show requests."""

        self.show_calls += 1

    def move_active_chip(self, intent: PromptReorderKeyboardMoveIntent) -> bool:
        """Record one typed keyboard reorder request."""

        return self._record_keyboard_move(intent.direction)

    def _record_keyboard_move(self, direction: str) -> bool:
        """Apply a configured keyboard snapshot for one controller test move."""

        self.keyboard_move_calls.append(direction)
        moved = self.keyboard_move_results.get(direction, True)
        if not moved:
            return False
        snapshot = self.keyboard_move_snapshots.get(direction)
        if snapshot is not None:
            self._ordered_indices = list(snapshot.ordered_chip_indices)
            self._active_segment_index = snapshot.active_segment_index
            self._dragged_segment_index = snapshot.dragged_segment_index
            self._current_layout_view = snapshot.layout_view
            if snapshot.reorder_state is not None:
                self._current_reorder_state = snapshot.reorder_state
            self._has_reordered = snapshot.has_reordered
        return True


class PreviewSyncContextDouble:
    """Publish scheduling context from one configured overlay generation."""

    def __init__(
        self,
        overlay: OverlayDouble,
        metrics: PromptReorderInteractionMetricsOwner,
    ) -> None:
        """Store the focused test authorities used by context publication."""

        self._overlay = overlay
        self._metrics = metrics
        self.snapshot_calls = 0

    def snapshot(self) -> PromptReorderPreviewSyncContext:
        """Return one scheduling context and consume one-shot shadow feedback."""

        self.snapshot_calls += 1
        overlay = self._overlay
        dragged_segment_index = overlay._dragged_segment_index
        base_drag_layout_ready = overlay._base_drag_layout_view is not None
        pointer_drag_ready = (
            dragged_segment_index is not None and base_drag_layout_ready
        )
        requires_initial_landing_shadow = False
        if pointer_drag_ready:
            requires_initial_landing_shadow = (
                overlay._should_flush_initial_landing_shadow_sync
            )
            overlay._should_flush_initial_landing_shadow_sync = False
        return PromptReorderPreviewSyncContext(
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            pointer_active=self._metrics.pointer_loop_active,
            dragged_segment_index=dragged_segment_index,
            base_drag_layout_ready=base_drag_layout_ready,
            requires_immediate_drag_geometry=(
                pointer_drag_ready and not overlay._has_base_drag_placement_geometry
            ),
            requires_initial_landing_shadow=requires_initial_landing_shadow,
        )


class OverlayFactoryDouble:
    """Create deterministic reorder overlay doubles."""

    def __init__(
        self,
        overlay: OverlayDouble | None = None,
        *,
        interaction_metrics: PromptReorderInteractionMetricsOwner | None = None,
    ) -> None:
        """Initialize the factory with an optional prebuilt overlay."""

        self.overlay = overlay or OverlayDouble()
        self.interaction_metrics = (
            interaction_metrics or PromptReorderInteractionMetricsOwner()
        )
        self.preview_sync_context = PreviewSyncContextDouble(
            self.overlay,
            self.interaction_metrics,
        )
        self.create_calls: list[tuple[object, object]] = []

    def create_segment_overlay(
        self,
        editor: object,
        *,
        layout_policy: object,
    ) -> PromptReorderOverlayAssembly:
        """Return configured overlay authorities and record construction inputs."""

        self.create_calls.append((editor, layout_policy))
        return PromptReorderOverlayAssembly(
            overlay=self.overlay,
            preview_build_facts=self.overlay,
            preview_sync_context=self.preview_sync_context,
            preview_layout_changed=self.overlay.previewLayoutChanged,
        )
