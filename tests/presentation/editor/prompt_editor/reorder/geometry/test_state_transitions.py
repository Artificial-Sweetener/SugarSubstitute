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

"""Verify prompt reorder geometry state transitions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_identity import (
    reorder_preview_geometry_matches_target,
    reorder_preview_target_identity,
    reorder_preview_target_identity_context,
)

from .support import (
    _FakeLayoutPolicy,
    _geometry_owner,
    _document_view,
    _layout_view,
    _state_view,
)


def test_reorder_geometry_state_rejects_stale_preview_identity_atomically() -> None:
    """A new session should atomically retire every previous preview identity."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    layout_view = _layout_view()
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        layout_view,
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    assert (
        owner.begin_drag(
            dragged_segment_index=0,
            gesture_id=None,
            event_id=None,
        )
        is not None
    )
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=target,
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    preview_identity = owner.state.preview_layout_target_identity
    assert preview_identity is not None
    identity_context = reorder_preview_target_identity_context(
        preview_identity,
        prefix="preview_geometry_target",
    )
    assert "alpha, beta, gamma" not in repr(identity_context)
    assert preview_identity == reorder_preview_target_identity(
        owner.state,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )

    owner.set_session(
        _document_view("alpha, beta, gamma, delta"),
        layout_view,
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    assert owner.state.preview_layout_target_identity is None
    assert owner.state.preview_geometry_target_identity is None
    assert not reorder_preview_geometry_matches_target(
        owner.state,
        dragged_segment_index=0,
        target=target,
        viewport_identity=("viewport", 320, 180, 0),
    )


def test_reorder_geometry_state_is_frozen_and_replaced_per_transition() -> None:
    """Callers should observe complete publications and cannot mutate them."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    initial_state = owner.state
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        _layout_view(),
        _state_view(),
        ordered_indices=(0, 1, 2),
    )
    session_state = owner.state

    assert session_state is not initial_state
    assert session_state.current_layout_view is session_state.original_layout_view
    assert session_state.current_reorder_state is session_state.original_reorder_state
    assert session_state.ordered_segment_indices == (0, 1, 2)
    with pytest.raises(FrozenInstanceError):
        setattr(session_state, "ordered_segment_indices", (2, 1, 0))
    assert owner.state is session_state


def test_reorder_geometry_commit_and_restore_publish_coherent_state() -> None:
    """Commit and cancel transitions should never expose mixed layout generations."""

    owner = PromptReorderInteractionGeometry(
        layout_policy=_FakeLayoutPolicy(),
        geometry_owner=_geometry_owner(),
    )
    original_layout = _layout_view()
    original_state = _state_view()
    owner.set_session(
        _document_view("alpha, beta, gamma"),
        original_layout,
        original_state,
        ordered_indices=(0, 1, 2),
    )
    owner.begin_drag(dragged_segment_index=0, gesture_id=None, event_id=None)
    owner.update_preview_layout(
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=1),
        viewport_identity=("viewport", 320, 180, 0),
        gesture_id=None,
        event_id=None,
    )
    preview_state = owner.state

    assert preview_state.preview_layout_view is not None
    assert preview_state.preview_reorder_state is not None
    assert preview_state.preview_layout_target_identity is not None
    assert preview_state.ordered_segment_indices == (1, 0, 2)
    assert owner.commit_preview_layout()
    committed_state = owner.state
    assert committed_state is not preview_state
    assert committed_state.current_layout_view is preview_state.preview_layout_view
    assert committed_state.current_reorder_state is preview_state.preview_reorder_state
    assert committed_state.ordered_segment_indices == (1, 0, 2)

    owner.clear_drag_context(preserve_preview=True)
    completed_state = owner.state
    assert completed_state.current_layout_view is committed_state.current_layout_view
    assert (
        completed_state.current_reorder_state is committed_state.current_reorder_state
    )
    assert completed_state.preview_layout_view is committed_state.preview_layout_view
    assert (
        completed_state.preview_reorder_state is committed_state.preview_reorder_state
    )
    assert completed_state.base_drag_layout_view is None
    assert completed_state.base_drag_reorder_state is None
    assert completed_state.placement_snapshot is None

    owner.restore_original_layout()
    restored_state = owner.state
    assert restored_state.current_layout_view is original_layout
    assert restored_state.current_reorder_state is original_state
    assert restored_state.preview_layout_view is None
    assert restored_state.preview_reorder_state is None
    assert restored_state.preview_layout_target_identity is None
    assert restored_state.preview_geometry_target_identity is None
    assert restored_state.ordered_segment_indices == (0, 1, 2)
