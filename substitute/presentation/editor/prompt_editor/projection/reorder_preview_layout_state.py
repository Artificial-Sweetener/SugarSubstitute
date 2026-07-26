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

"""Own target-driven reorder preview layout state transitions."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
    PromptReorderPreparedStateView,
)

from .observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
    reorder_drag_target_kind,
)
from .reorder_interaction_geometry_identity import reorder_preview_target_identity
from .reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from .reorder_keyboard_navigation import PromptReorderLayoutPolicy
from .reorder_preview_layout_policy import reorder_layout_for_painted_preview


class PromptReorderPreviewLayoutStateOwner:
    """Build one coherent preview layout, reorder state, identity, and chip order."""

    def __init__(self, *, layout_policy: PromptReorderLayoutPolicy) -> None:
        """Store the application layout policy used by preview transitions."""

        self._layout_policy = layout_policy

    def build(
        self,
        state: PromptReorderInteractionGeometryState,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: object | None,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderInteractionGeometryState:
        """Return the complete preview layout state for one active target."""

        total_started_at = reorder_drag_started_at()
        built_preview_layout = False
        document_view = state.document_view
        if document_view is None:
            return state

        preview_layout_view = state.preview_layout_view
        preview_reorder_state = state.preview_reorder_state
        preview_layout_target_identity = state.preview_layout_target_identity
        if (
            dragged_segment_index is not None
            and state.base_drag_layout_view is not None
        ):
            if active_target is not None:
                started_at = reorder_drag_started_at()
                if state.base_drag_reorder_state is None:
                    return state
                preview_state = self._layout_policy.build_preview_drop_state(
                    document_view,
                    PromptReorderPreparedStateView(
                        reorder_state=state.base_drag_reorder_state,
                        layout_view=state.base_drag_layout_view,
                    ),
                    dragged_segment_index=dragged_segment_index,
                    drop_target=active_target,
                )
                preview_layout_view = preview_state.layout_view
                preview_reorder_state = preview_state.reorder_state
                preview_layout_target_identity = reorder_preview_target_identity(
                    state,
                    dragged_segment_index=dragged_segment_index,
                    target=active_target,
                    viewport_identity=viewport_identity,
                    preview_layout_view=preview_layout_view,
                )
                built_preview_layout = True
                log_reorder_drag_timing(
                    "preview_layout.build_drop_layout",
                    started_at=started_at,
                    gesture_id=gesture_id,
                    event_id=event_id,
                    dragged_segment_index=dragged_segment_index,
                    target_kind=reorder_drag_target_kind(active_target),
                    row_count=len(preview_layout_view.rows),
                    gap_count=len(preview_layout_view.gaps),
                )
            else:
                preview_layout_view = state.base_drag_layout_view
                preview_reorder_state = state.base_drag_reorder_state
                preview_layout_target_identity = None

        preview_layout = reorder_layout_for_painted_preview(
            state,
            dragged_segment_index=dragged_segment_index,
            preview_layout_view=preview_layout_view,
        )
        if preview_layout is None:
            ordered_segment_indices = state.initial_ordered_indices
            preview_layout_target_identity = None
            preview_reorder_state = None
        else:
            started_at = reorder_drag_started_at()
            ordered_segment_indices = self._layout_policy.reorder_layout_chip_indices(
                preview_layout
            )
            order_elapsed_ms = log_reorder_drag_timing(
                "preview_layout.order_indices",
                started_at=started_at,
                gesture_id=gesture_id,
                event_id=event_id,
                ordered_count=len(ordered_segment_indices),
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
                ordered_count=len(ordered_segment_indices),
                order_elapsed_ms=f"{order_elapsed_ms:.3f}",
            )
            return replace(
                state,
                preview_layout_view=preview_layout_view,
                preview_reorder_state=preview_reorder_state,
                preview_layout_target_identity=preview_layout_target_identity,
                ordered_segment_indices=ordered_segment_indices,
            )

        next_state = replace(
            state,
            preview_layout_view=preview_layout_view,
            preview_reorder_state=preview_reorder_state,
            preview_layout_target_identity=preview_layout_target_identity,
            ordered_segment_indices=ordered_segment_indices,
        )
        log_reorder_drag_timing(
            "preview_layout.total",
            started_at=total_started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            dragged_segment_index=dragged_segment_index,
            target_kind=reorder_drag_target_kind(active_target),
            built_preview_layout=built_preview_layout,
            preview_active=False,
            ordered_count=len(ordered_segment_indices),
        )
        return next_state


__all__ = ["PromptReorderPreviewLayoutStateOwner"]
