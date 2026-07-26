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

"""Map prompt reorder gesture facts into immutable visual interaction state."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt

from .chip_painter import PromptChipPaintStyle
from .reorder_visual_style import PromptReorderVisualStyle


@dataclass(frozen=True, slots=True)
class PromptReorderChipInteractionState:
    """Describe logical interaction state for one pointer region."""

    segment_index: int
    active: bool
    dragging: bool
    hovered: bool
    pressed: bool
    cursor_shape: Qt.CursorShape
    style: PromptChipPaintStyle


def prompt_reorder_chip_interaction_state(
    segment_index: int,
    *,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    pressed_segment_index: int | None,
) -> PromptReorderChipInteractionState:
    """Map gesture state to one logical pointer region."""

    active = segment_index == active_segment_index
    dragging = segment_index == dragged_segment_index
    hovered = segment_index == hovered_segment_index
    pressed = segment_index == pressed_segment_index
    cursor_shape = (
        Qt.CursorShape.ClosedHandCursor
        if dragging or pressed
        else Qt.CursorShape.OpenHandCursor
    )
    return PromptReorderChipInteractionState(
        segment_index=segment_index,
        active=active,
        dragging=dragging,
        hovered=hovered,
        pressed=pressed,
        cursor_shape=cursor_shape,
        style=visual_style.paint_style_for_segment(
            segment_index,
            dragged_segment_index=dragged_segment_index,
            hovered_segment_index=hovered_segment_index,
            active_segment_index=active_segment_index,
        ),
    )


def prompt_reorder_chip_interaction_states(
    segment_indices: Sequence[int],
    *,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    pressed_segment_index: int | None,
) -> tuple[PromptReorderChipInteractionState, ...]:
    """Map gesture state to every visible logical pointer region."""

    return tuple(
        prompt_reorder_chip_interaction_state(
            segment_index,
            visual_style=visual_style,
            dragged_segment_index=dragged_segment_index,
            hovered_segment_index=hovered_segment_index,
            active_segment_index=active_segment_index,
            pressed_segment_index=pressed_segment_index,
        )
        for segment_index in segment_indices
    )


__all__ = [
    "PromptReorderChipInteractionState",
    "prompt_reorder_chip_interaction_state",
    "prompt_reorder_chip_interaction_states",
]
