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

"""Verify prompt reorder geometry drag preparation."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.projection.reorder_drag_geometry_preparation import (
    PromptReorderDragGeometryPreparationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_geometry_publication import (
    PromptReorderDropGeometryPublisher,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)

from .support import (
    _FakeLayoutPolicy,
    _FakeDragGeometrySource,
    _empty_chip_snapshot,
    _placement_snapshot,
    _session_geometry_state,
)


def test_drag_geometry_preparation_begins_one_coherent_drag_generation() -> None:
    """Base layout, reorder state, and stale preview values should change atomically."""

    geometry_source = _FakeDragGeometrySource(
        chip_snapshot=_empty_chip_snapshot(),
        placement_snapshot=_placement_snapshot(populated=False),
    )
    owner = PromptReorderDragGeometryPreparationOwner(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=geometry_source,
        drop_geometry=PromptReorderDropGeometryPublisher(),
    )
    missing_session = PromptReorderInteractionGeometryState()

    assert (
        owner.begin_drag(
            missing_session,
            dragged_segment_index=0,
            gesture_id=None,
            event_id=None,
        )
        is missing_session
    )

    state = _session_geometry_state()
    next_state = owner.begin_drag(
        state,
        dragged_segment_index=0,
        gesture_id=3,
        event_id=5,
    )

    assert next_state is not state
    assert next_state.base_drag_layout_view is not None
    assert next_state.base_drag_layout_view.rows[0].chip_indices == (1, 2)
    assert next_state.base_drag_reorder_state is not None
    assert next_state.base_drag_reorder_state.ordered_chip_indices == (1, 2)
    assert next_state.preview_layout_view is None
    assert next_state.preview_reorder_state is None
    assert next_state.preview_layout_target_identity is None
    assert next_state.preview_geometry_target_identity is None
    assert next_state.placement_snapshot is None
    assert next_state.active_placement is None


def test_drag_geometry_preparation_primes_only_nonempty_painted_geometry() -> None:
    """Placement priming should be identity-safe and publish lanes atomically."""

    geometry_source = _FakeDragGeometrySource(
        chip_snapshot=_empty_chip_snapshot(),
        placement_snapshot=_placement_snapshot(populated=False),
    )
    owner = PromptReorderDragGeometryPreparationOwner(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=geometry_source,
        drop_geometry=PromptReorderDropGeometryPublisher(),
    )
    state = _session_geometry_state()
    chip_snapshot = geometry_source.chip_snapshot

    assert (
        owner.prime_from_painted_projection(
            state,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index={},
            gesture_id=None,
            event_id=None,
        )
        is state
    )
    assert geometry_source.live_placement_query_count == 0

    drag_state = owner.begin_drag(
        state,
        dragged_segment_index=0,
        gesture_id=None,
        event_id=None,
    )
    assert (
        owner.prime_from_painted_projection(
            drag_state,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index={},
            gesture_id=None,
            event_id=None,
        )
        is drag_state
    )
    assert geometry_source.live_placement_query_count == 1

    geometry_source.placement_snapshot = _placement_snapshot(populated=True)
    primed_state = owner.prime_from_painted_projection(
        drag_state,
        chip_geometry_snapshot=chip_snapshot,
        gap_ranges_by_index={},
        gesture_id=3,
        event_id=6,
    )

    assert primed_state is not drag_state
    assert primed_state.placement_snapshot is not None
    assert len(primed_state.placement_snapshot.placements) == 1
    assert len(primed_state.drop_target_visuals) == 1
    assert len(primed_state.drop_target_lanes) == 1
    assert geometry_source.live_placement_query_count == 2
