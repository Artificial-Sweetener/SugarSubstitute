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

"""Characterize coherent preview-build fact publication."""

from __future__ import annotations

from dataclasses import dataclass, replace

from substitute.application.prompt_editor.document.service import PromptDocumentService
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_build_facts import (
    PromptReorderPreviewBuildFactsOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


@dataclass(frozen=True, slots=True)
class _GestureState:
    """Provide immutable gesture facts to the owner."""

    active_segment_index: int | None
    dragged_segment_index: int | None
    active_drop_target: PromptReorderDropTarget | None


@dataclass(slots=True)
class _Gesture:
    """Publish one replaceable gesture generation."""

    state: _GestureState


@dataclass(slots=True)
class _Geometry:
    """Publish one replaceable geometry generation."""

    state: PromptReorderInteractionGeometryState


@dataclass(slots=True)
class _Keyboard:
    """Return one configured keyboard commit target."""

    target: PromptReorderDropTarget | None
    query_count: int = 0

    def committable_drop_target(self) -> PromptReorderDropTarget | None:
        """Return the configured target and count the query."""

        self.query_count += 1
        return self.target


def test_pointer_preview_facts_use_one_active_geometry_generation() -> None:
    """Pointer facts should preserve preview state, order, and target together."""

    state = _state()
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    keyboard = _Keyboard(PromptLineDropTarget(row_index=0, insertion_index=2))
    geometry = _Geometry(state)
    gesture = _Gesture(_GestureState(None, 0, target))
    owner = PromptReorderPreviewBuildFactsOwner(
        geometry_state=lambda: geometry.state,
        gesture_facts=lambda: (
            gesture.state.active_segment_index,
            gesture.state.dragged_segment_index,
            gesture.state.active_drop_target,
        ),
        keyboard_drop_target=keyboard.committable_drop_target,
    )

    facts = owner.snapshot()

    assert facts.preview_layout_view is state.preview_layout_view
    assert facts.base_drag_layout_view is state.base_drag_layout_view
    assert facts.preview_reorder_state is state.preview_reorder_state
    assert facts.base_drag_reorder_state is state.base_drag_reorder_state
    assert facts.ordered_chip_indices is state.ordered_segment_indices
    assert facts.dragged_segment_index == 0
    assert facts.drop_target is target
    assert keyboard.query_count == 0


def test_keyboard_preview_facts_resolve_layout_target_without_pointer_state() -> None:
    """Keyboard facts should resolve the committed target only after a reorder."""

    state = _state()
    target = PromptLineDropTarget(row_index=0, insertion_index=1)
    keyboard = _Keyboard(target)
    geometry = _Geometry(state)
    gesture = _Gesture(_GestureState(0, None, target))
    owner = PromptReorderPreviewBuildFactsOwner(
        geometry_state=lambda: geometry.state,
        gesture_facts=lambda: (
            gesture.state.active_segment_index,
            gesture.state.dragged_segment_index,
            gesture.state.active_drop_target,
        ),
        keyboard_drop_target=keyboard.committable_drop_target,
    )

    facts = owner.snapshot()

    assert facts.preview_layout_view is state.current_layout_view
    assert facts.preview_reorder_state is state.preview_reorder_state
    assert facts.dragged_segment_index is None
    assert facts.drop_target is target
    assert keyboard.query_count == 1


def test_base_only_preview_facts_skip_keyboard_target_resolution() -> None:
    """An unchanged base-drag frame should publish no active target or preview state."""

    state = _state()
    state = replace(
        state,
        current_layout_view=state.original_layout_view,
        current_reorder_state=state.original_reorder_state,
    )
    keyboard = _Keyboard(PromptLineDropTarget(row_index=0, insertion_index=1))
    geometry = _Geometry(state)
    gesture = _Gesture(_GestureState(None, None, None))
    owner = PromptReorderPreviewBuildFactsOwner(
        geometry_state=lambda: geometry.state,
        gesture_facts=lambda: (
            gesture.state.active_segment_index,
            gesture.state.dragged_segment_index,
            gesture.state.active_drop_target,
        ),
        keyboard_drop_target=keyboard.committable_drop_target,
    )

    facts = owner.snapshot()

    assert facts.preview_layout_view is None
    assert facts.preview_reorder_state is None
    assert facts.base_drag_layout_view is state.base_drag_layout_view
    assert facts.base_drag_reorder_state is state.base_drag_reorder_state
    assert facts.drop_target is None
    assert keyboard.query_count == 0


def _state() -> PromptReorderInteractionGeometryState:
    """Return one coherent application-backed geometry generation."""

    service = PromptDocumentService()
    document = service.build_document_view("alpha, beta")
    session = service.build_reorder_session_view(document)
    base = service.build_base_drag_state(
        document,
        session.reorder_state,
        current_layout_view=session.layout_view,
        dragged_segment_index=0,
    )
    preview = service.build_preview_drop_state(
        document,
        base,
        dragged_segment_index=0,
        drop_target=PromptLineDropTarget(row_index=0, insertion_index=1),
    )
    return PromptReorderInteractionGeometryState(
        document_view=document,
        original_layout_view=session.layout_view,
        current_layout_view=preview.layout_view,
        base_drag_layout_view=base.layout_view,
        preview_layout_view=preview.layout_view,
        original_reorder_state=session.reorder_state,
        current_reorder_state=preview.reorder_state,
        base_drag_reorder_state=base.reorder_state,
        preview_reorder_state=preview.reorder_state,
        initial_ordered_indices=(0, 1),
        ordered_segment_indices=(1, 0),
    )
