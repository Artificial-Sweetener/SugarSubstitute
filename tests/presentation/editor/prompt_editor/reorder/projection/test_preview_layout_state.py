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

"""Verify target-driven reorder preview-layout state ownership."""

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_layout_state import (
    PromptReorderPreviewLayoutStateOwner,
)


def test_preview_layout_state_returns_same_publication_without_document() -> None:
    """Unavailable session inputs should perform no work or allocation."""

    state = PromptReorderInteractionGeometryState()
    owner = PromptReorderPreviewLayoutStateOwner(layout_policy=PromptDocumentService())

    result = owner.build(
        state,
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=0),
        viewport_identity=("viewport", 320, 180),
        gesture_id=4,
        event_id=7,
    )

    assert result is state


def test_preview_layout_state_builds_target_layout_and_identity_together() -> None:
    """An active target should publish matching layout, state, identity, and order."""

    document_service, state = _active_drag_state()
    owner = PromptReorderPreviewLayoutStateOwner(layout_policy=document_service)

    result = owner.build(
        state,
        dragged_segment_index=0,
        active_target=PromptLineDropTarget(row_index=0, insertion_index=2),
        viewport_identity=("viewport", 320, 180),
        gesture_id=4,
        event_id=7,
    )

    assert result is not state
    assert result.preview_layout_view is not None
    assert result.preview_reorder_state is not None
    assert result.preview_layout_target_identity is not None
    assert result.ordered_segment_indices == (
        document_service.reorder_layout_chip_indices(result.preview_layout_view)
    )
    assert (
        result.preview_reorder_state.ordered_chip_indices
        == result.ordered_segment_indices
    )


def test_preview_layout_state_uses_base_layout_without_active_target() -> None:
    """Pre-target drag state should publish the exact base layout and order."""

    document_service, state = _active_drag_state()
    owner = PromptReorderPreviewLayoutStateOwner(layout_policy=document_service)

    result = owner.build(
        state,
        dragged_segment_index=0,
        active_target=None,
        viewport_identity=("viewport", 320, 180),
        gesture_id=4,
        event_id=7,
    )

    assert result.preview_layout_view is state.base_drag_layout_view
    assert result.preview_reorder_state is state.base_drag_reorder_state
    assert result.preview_layout_target_identity is None
    assert state.base_drag_layout_view is not None
    assert result.ordered_segment_indices == (
        document_service.reorder_layout_chip_indices(state.base_drag_layout_view)
    )


def _active_drag_state() -> tuple[
    PromptDocumentService,
    PromptReorderInteractionGeometryState,
]:
    """Return a real application reorder session with prepared base-drag state."""

    document_service = PromptDocumentService()
    document_view = document_service.build_document_view("alpha, beta, gamma")
    session = document_service.build_reorder_session_view(document_view)
    dragged_segment_index = 0
    base = document_service.build_base_drag_state(
        document_view,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=dragged_segment_index,
    )
    return document_service, PromptReorderInteractionGeometryState(
        document_view=document_view,
        original_layout_view=session.layout_view,
        current_layout_view=session.layout_view,
        base_drag_layout_view=base.layout_view,
        original_reorder_state=session.reorder_state,
        current_reorder_state=session.reorder_state,
        base_drag_reorder_state=base.reorder_state,
        initial_ordered_indices=(0, 1, 2),
        ordered_segment_indices=(0, 1, 2),
    )
