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

"""Verify prompt reorder chip paint state contracts."""

from __future__ import annotations


from substitute.presentation.editor.prompt_editor.overlays.reorder_render_state import (
    prompt_reorder_chip_paint_states,
)

from .support import (
    _style,
    _visual,
)


def test_chip_paint_states_map_visual_state_to_styles() -> None:
    """Chip paint construction should apply active, dragged, and hovered styles."""

    visual_style = _style()
    states = prompt_reorder_chip_paint_states(
        (0, 1, 2),
        geometries_by_index={},
        visuals_by_index={0: _visual(0.0), 1: _visual(40.0), 2: _visual(80.0)},
        visual_style=visual_style,
        dragged_segment_index=1,
        hovered_segment_index=2,
        active_segment_index=0,
        skip_dragged_segment=False,
    )

    assert [state.segment_index for state in states] == [0, 1, 2]
    assert states[0].style.fill_color == visual_style.active_fill
    assert states[1].style.fill_color == visual_style.drag_fill
    assert states[2].style.fill_color == visual_style.hover_fill


def test_preview_chip_paint_states_skip_dragged_segment() -> None:
    """Preview paint state should omit the lifted chip while preserving order."""

    states = prompt_reorder_chip_paint_states(
        (2, 1, 0),
        geometries_by_index={},
        visuals_by_index={0: _visual(0.0), 1: _visual(40.0), 2: _visual(80.0)},
        visual_style=_style(),
        dragged_segment_index=1,
        hovered_segment_index=None,
        active_segment_index=None,
        skip_dragged_segment=True,
    )

    assert [state.segment_index for state in states] == [2, 0]
