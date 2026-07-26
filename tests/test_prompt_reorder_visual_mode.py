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

"""Cover authoritative reorder prepared-visual mode selection."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint

from substitute.application.prompt_editor.reorder.views import (
    PromptLineDropTarget,
    PromptReorderLayoutView,
    PromptReorderStateView,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Geometry:
    """Publish replaceable immutable interaction geometry state."""

    def __init__(self) -> None:
        """Initialize an empty unreordered publication."""

        self.state = PromptReorderInteractionGeometryState()


def test_visual_mode_selects_drag_preview_layout() -> None:
    """Pointer drag painting must consume the prepared preview layout."""

    geometry = _Geometry()
    preview_layout = cast(PromptReorderLayoutView, object())
    geometry.state = PromptReorderInteractionGeometryState(
        preview_layout_view=preview_layout,
    )
    gesture = PromptReorderGestureController()
    gesture.begin_pointer_drag(segment_index=1, global_position=QPoint(20, 20))
    owner = PromptReorderVisualModeOwner(
        geometry_state=lambda: geometry.state,
        gesture=gesture,
    )

    assert owner.painted_preview_layout() is preview_layout
    assert owner.preview_active() is True


def test_visual_mode_selects_keyboard_or_committed_current_layout() -> None:
    """Keyboard targets and prospective committed order use current layout."""

    geometry = _Geometry()
    current_layout = cast(PromptReorderLayoutView, object())
    original_state = cast(PromptReorderStateView, object())
    current_state = cast(PromptReorderStateView, object())
    geometry.state = PromptReorderInteractionGeometryState(
        current_layout_view=current_layout,
        original_reorder_state=original_state,
        current_reorder_state=original_state,
    )
    gesture = PromptReorderGestureController()
    gesture.activate_segment(1)
    gesture.set_active_drop_target(PromptLineDropTarget(row_index=0, insertion_index=0))
    owner = PromptReorderVisualModeOwner(
        geometry_state=lambda: geometry.state,
        gesture=gesture,
    )

    assert owner.painted_preview_layout() is current_layout

    gesture.reset_all()
    geometry.state = PromptReorderInteractionGeometryState(
        current_layout_view=current_layout,
        original_reorder_state=original_state,
        current_reorder_state=current_state,
    )

    assert owner.painted_preview_layout() is current_layout
    assert owner.has_reordered() is True


def test_visual_mode_keeps_unreordered_idle_session_live() -> None:
    """An idle unchanged session must not claim preview paint ownership."""

    state = cast(PromptReorderStateView, object())
    geometry = _Geometry()
    geometry.state = PromptReorderInteractionGeometryState(
        current_layout_view=cast(PromptReorderLayoutView, object()),
        original_reorder_state=state,
        current_reorder_state=state,
    )
    owner = PromptReorderVisualModeOwner(
        geometry_state=lambda: geometry.state,
        gesture=PromptReorderGestureController(),
    )

    assert owner.painted_preview_layout() is None
    assert owner.preview_active() is False
    assert owner.has_reordered() is False
