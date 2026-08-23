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

"""Verify prompt reorder visual style contracts."""

from __future__ import annotations


from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    contrast_ratio,
    readable_surface_text_color,
)

from .support import (
    _style,
)


def test_reorder_visual_style_reuses_prepared_interaction_styles() -> None:
    """Repeated state mapping should not reconstruct equivalent Qt colors."""

    visual_style = _style()

    first_rest = visual_style.paint_style_for_segment(
        0,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )
    second_rest = visual_style.paint_style_for_segment(
        1,
        dragged_segment_index=None,
        hovered_segment_index=None,
        active_segment_index=None,
    )
    dragged = visual_style.paint_style_for_segment(
        1,
        dragged_segment_index=1,
        hovered_segment_index=None,
        active_segment_index=None,
    )

    assert first_rest is second_rest
    assert dragged is not first_rest
    assert dragged.fill_color == visual_style.drag_fill
    assert dragged.border_color == visual_style.drag_border


def test_reorder_overlay_prefers_readable_proxy_text_on_dark_surfaces() -> None:
    """Drag proxy text falls back to a readable tone when the palette lies."""

    dark_surface = QColor(22, 24, 27)
    unreadable_preferred = QColor(0, 0, 0)

    resolved = readable_surface_text_color(
        preferred=unreadable_preferred,
        background=dark_surface,
    )

    assert resolved != unreadable_preferred
    assert contrast_ratio(resolved, dark_surface) >= 4.5
