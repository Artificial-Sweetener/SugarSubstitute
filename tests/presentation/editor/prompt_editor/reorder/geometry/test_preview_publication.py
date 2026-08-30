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

"""Verify prompt reorder geometry preview publication."""

from __future__ import annotations


from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderPreviewSnapshot,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_identity import (
    reorder_preview_target_identity,
)

from .support import (
    _FakeLayoutPolicy,
    _geometry_owner,
    _document_view,
    _layout_view,
    _state_view,
    _session_geometry_state,
)


def test_preview_snapshot_publication_adopts_identity_and_order_atomically() -> None:
    """A prepared preview should replace snapshot, identity, and order together."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        _layout_view(),
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    snapshot = PromptReorderPreviewSnapshot(
        text="beta, alpha, gamma",
        chip_ranges_by_index={},
        chip_rendered_ranges_by_index={},
        chip_owned_ranges_by_index={},
        gap_ranges_by_index={},
    )
    previous_state = owner.state

    owner.set_preview_snapshots(
        snapshot,
        base_drag_snapshot=snapshot,
        ordered_chip_indices=(1, 0, 2),
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )

    result = owner.state
    assert result is not previous_state
    assert result.preview_snapshot is snapshot
    assert result.base_drag_snapshot is snapshot
    assert result.ordered_segment_indices == (1, 0, 2)
    assert result.preview_layout_target_identity == reorder_preview_target_identity(
        result,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )


def test_preview_snapshot_clear_retires_only_stale_geometry_identity() -> None:
    """Clearing a frame should preserve layout truth while rejecting stale geometry."""

    state = _session_geometry_state()
    assert state.document_view is not None
    assert state.current_layout_view is not None
    assert state.current_reorder_state is not None
    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    owner.set_session(
        state.document_view,
        state.current_layout_view,
        state.current_reorder_state,
        ordered_indices=state.ordered_segment_indices,
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    owner.set_preview_snapshots(
        None,
        base_drag_snapshot=None,
        ordered_chip_indices=(2, 1, 0),
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
    )

    result = owner.state
    assert result.preview_snapshot is None
    assert result.base_drag_snapshot is None
    assert result.ordered_segment_indices == (1, 0, 2)
    assert result.preview_layout_target_identity is not None
    assert result.preview_geometry_target_identity is None
