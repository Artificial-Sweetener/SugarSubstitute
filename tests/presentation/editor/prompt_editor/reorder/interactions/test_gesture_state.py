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

"""Verify typed gesture-state publication through reorder interactions."""

from PySide6.QtCore import QPoint, QPointF, QRectF

from substitute.application.prompt_editor.reorder.views import PromptLineDropTarget
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)


def test_gesture_controller_exposes_pointer_and_keyboard_state() -> None:
    """Publish typed pointer and keyboard state without QWidget access."""

    gesture = PromptReorderGestureController()
    target = PromptLineDropTarget(row_index=0, insertion_index=0)

    gesture.activate_segment(1)
    assert gesture.begin_pointer_drag(
        segment_index=1,
        global_position=QPoint(20, 30),
    )
    gesture.capture_drag_intent_context(
        chip_rect=QRectF(10.0, 10.0, 50.0, 20.0),
        local_pointer=QPointF(25.0, 18.0),
    )
    assert gesture.set_active_drop_target(target)
    gesture.set_keyboard_preferred_x(18.0)

    pointer_state = gesture.pointer_state()
    keyboard_state = gesture.keyboard_state()

    assert pointer_state.dragged_segment_index == 1
    assert pointer_state.active_drop_target == target
    assert pointer_state.drag_grab_offset == QPointF(15.0, 8.0)
    assert keyboard_state.active_segment_index == 1
    assert keyboard_state.active_drop_target == target
    assert keyboard_state.keyboard_preferred_x == 18.0
