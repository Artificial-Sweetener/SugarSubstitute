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

"""Verify typed keyboard reorder interaction ownership."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import cast

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.document.views import (
    PromptDocumentView,
    PromptRegionStructureView,
)
from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderDropTarget,
    PromptReorderLayoutView,
    PromptReorderRowView,
)
from substitute.presentation.editor.prompt_editor.overlays.chip_visuals import (
    PromptChipVisual,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_displacement_intent import (
    ReorderDisplacementIntent,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_keyboard_interaction import (
    PromptReorderKeyboardInteractionOwner,
    PromptReorderKeyboardVisualContext,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_drop_targets import (
    PromptReorderRowDropLane,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_keyboard_navigation import (
    PromptReorderKeyboardNavigationResult,
)


def _document() -> PromptDocumentView:
    """Return a minimal document publication for keyboard readiness."""

    return PromptDocumentView(
        source_text="tag",
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        region_structure=PromptRegionStructureView.empty(3),
        has_trailing_comma=False,
    )


def _layout() -> PromptReorderLayoutView:
    """Return one populated reorder row."""

    return PromptReorderLayoutView(
        rows=(PromptReorderRowView(row_index=0, chip_indices=(0, 1)),),
        gaps=(),
    )


class _KeyboardGeometry:
    """Provide deterministic prepared geometry to the keyboard owner."""

    def __init__(self) -> None:
        """Initialize one ready live layout without base-drag geometry."""

        self.state = PromptReorderInteractionGeometryState(
            document_view=_document(),
            current_layout_view=_layout(),
            ordered_segment_indices=(0, 1),
        )
        self.begin_count = 0
        self.horizontal_count = 0
        self.vertical_count = 0
        self.resolved_target = PromptLineDropTarget(row_index=0, insertion_index=1)

    def begin_drag(
        self,
        *,
        dragged_segment_index: int,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderLayoutView | None:
        """Publish stable base geometry for the active segment."""

        _ = dragged_segment_index, gesture_id, event_id
        self.begin_count += 1
        lane = PromptReorderRowDropLane(
            row_index=0,
            visual_row_index=0,
            hit_rect=QRectF(0.0, 0.0, 100.0, 20.0),
            slot_visuals=(),
        )
        self.state = replace(
            self.state,
            base_drag_layout_view=_layout(),
            drop_target_lanes=(lane,),
        )
        return self.state.base_drag_layout_view

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
        """Return one deterministic horizontal movement."""

        _ = (
            active_segment_index,
            active_target,
            preferred_x,
            step,
            gesture_id,
            event_id,
        )
        self.horizontal_count += 1
        return self._movement()

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
        """Return one deterministic vertical movement."""

        _ = (
            active_segment_index,
            active_target,
            direction,
            preferred_x,
            gesture_id,
            event_id,
        )
        self.vertical_count += 1
        return self._movement()

    def resolve_drop_target_for_current_layout(
        self,
        *,
        active_segment_index: int | None,
    ) -> PromptReorderDropTarget | None:
        """Return the target represented by the current order."""

        _ = active_segment_index
        return self.resolved_target

    def _movement(self) -> PromptReorderKeyboardNavigationResult:
        """Return a successful movement and publish its current layout."""

        self.state = replace(
            self.state,
            current_layout_view=_layout(),
            ordered_segment_indices=(1, 0),
        )
        return PromptReorderKeyboardNavigationResult(
            moved=True,
            destination_target=self.resolved_target,
            preferred_x=42.0,
            proposed_state=None,
            proposed_base_drag_state=None,
            ordered_segment_indices=(1, 0),
        )


class _KeyboardAnimation:
    """Capture keyboard displacement intents without a Qt presenter."""

    def __init__(self) -> None:
        """Initialize an empty intent list."""

        self.intents: list[ReorderDisplacementIntent] = []

    def record_target_change(
        self,
        intent: ReorderDisplacementIntent,
        *,
        segment_indices: Sequence[int],
        preview_active: bool,
        live_visuals_by_index: Mapping[int, PromptChipVisual],
        preview_visuals_by_index: Mapping[int, PromptChipVisual],
    ) -> None:
        """Capture one intent and consume its explicit visual context."""

        _ = (
            segment_indices,
            preview_active,
            live_visuals_by_index,
            preview_visuals_by_index,
        )
        self.intents.append(intent)


def test_keyboard_owner_prepares_context_once_and_publishes_moves() -> None:
    """Repeated keyboard moves should reuse base geometry and update gesture state."""

    geometry = _KeyboardGeometry()
    gesture = PromptReorderGestureController()
    gesture.activate_segment(0)
    animation = _KeyboardAnimation()
    owner = PromptReorderKeyboardInteractionOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=gesture,
        animation=cast(PromptReorderAnimationPresentationOwner, animation),
    )
    visuals = PromptReorderKeyboardVisualContext(
        segment_indices=(0, 1),
        preview_active=False,
        live_visuals_by_index={},
        preview_visuals_by_index={},
    )

    first = owner.move(
        direction="right",
        gesture_id=7,
        event_id=2,
        visuals=visuals,
    )
    second = owner.move(
        direction="down",
        gesture_id=7,
        event_id=2,
        visuals=visuals,
    )

    assert first.moved and first.context_prepared
    assert second.moved and not second.context_prepared
    assert geometry.begin_count == 1
    assert geometry.horizontal_count == 1
    assert geometry.vertical_count == 1
    assert gesture.state.active_drop_target == geometry.resolved_target
    assert gesture.state.keyboard_preferred_x == 42.0
    assert [intent.source for intent in animation.intents] == ["keyboard", "keyboard"]
    assert owner.committable_drop_target() == geometry.resolved_target


def test_keyboard_owner_rejects_missing_active_context_without_side_effects() -> None:
    """Navigation without an active segment should not build geometry or animate."""

    geometry = _KeyboardGeometry()
    gesture = PromptReorderGestureController()
    animation = _KeyboardAnimation()
    owner = PromptReorderKeyboardInteractionOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=gesture,
        animation=cast(PromptReorderAnimationPresentationOwner, animation),
    )

    result = owner.move(
        direction="left",
        gesture_id=None,
        event_id=None,
        visuals=PromptReorderKeyboardVisualContext(
            segment_indices=(),
            preview_active=False,
            live_visuals_by_index={},
            preview_visuals_by_index={},
        ),
    )

    assert not result.moved
    assert not result.context_prepared
    assert geometry.begin_count == 0
    assert animation.intents == []
    assert owner.committable_drop_target() is None
