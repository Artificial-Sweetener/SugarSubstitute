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

"""Verify prompt reorder interaction state contracts."""

from __future__ import annotations


from PySide6.QtCore import Qt

from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_visual import (
    prompt_reorder_chip_interaction_state,
    prompt_reorder_chip_interaction_states,
)

from .support import (
    _style,
)


def test_chip_interaction_state_maps_overlay_properties_and_cursor() -> None:
    """Interaction state construction should leave mutation to the overlay caller."""

    visual_style = _style()
    pressed = prompt_reorder_chip_interaction_state(
        3,
        visual_style=visual_style,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
        pressed_segment_index=3,
    )
    hovered = prompt_reorder_chip_interaction_state(
        4,
        visual_style=visual_style,
        dragged_segment_index=None,
        hovered_segment_index=4,
        active_segment_index=None,
        pressed_segment_index=None,
    )

    assert pressed.pressed is True
    assert pressed.cursor_shape == Qt.CursorShape.ClosedHandCursor
    assert hovered.hovered is True
    assert hovered.cursor_shape == Qt.CursorShape.OpenHandCursor
    assert hovered.style.fill_color == visual_style.hover_fill


def test_chip_interaction_states_preserve_segment_index_order() -> None:
    """Interaction-state batches should follow the overlay-owned chip order."""

    states = prompt_reorder_chip_interaction_states(
        (4, 2),
        visual_style=_style(),
        dragged_segment_index=2,
        hovered_segment_index=None,
        active_segment_index=4,
        pressed_segment_index=None,
    )

    assert [state.segment_index for state in states] == [4, 2]
    assert states[0].active is True
    assert states[1].dragging is True
