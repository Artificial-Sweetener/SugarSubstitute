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

"""Tests for prompt-editor flow-layout geometry helpers."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from substitute.presentation.editor.prompt_editor.geometry import (
    flow_layout_insertion_index,
    flow_layout_rects,
)


def test_flow_layout_rects_clamp_items_to_available_width() -> None:
    """Preview chip layout never emits a rect wider than the content area."""

    rects = flow_layout_rects(
        [QSize(254, 26), QSize(120, 26)],
        content_rect=QRect(4, 4, 237, 88),
        horizontal_spacing=4,
    )

    assert rects[0].width() == 237
    assert all(rect.width() <= 237 for rect in rects)


def test_flow_layout_insertion_index_uses_row_midpoints() -> None:
    """Wrapped preview insertion follows row-local midpoint crossing."""

    item_rects = (
        QRect(4, 4, 80, 22),
        QRect(88, 4, 90, 22),
        QRect(4, 30, 70, 22),
    )

    assert flow_layout_insertion_index(item_rects, point=QPoint(20, 6)) == 0
    assert flow_layout_insertion_index(item_rects, point=QPoint(150, 6)) == 2
    assert flow_layout_insertion_index(item_rects, point=QPoint(10, 36)) == 2
