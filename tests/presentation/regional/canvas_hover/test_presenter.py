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

"""Verify transient regional hover presentation on CuteCanvas masks."""

from __future__ import annotations

from uuid import UUID, uuid4

from PySide6.QtGui import QColor

from substitute.domain.workflow import WorkflowState
from substitute.presentation.regional import region_color
from substitute.presentation.regional.canvas_hover_presenter import (
    RegionalCanvasHoverPresenter,
)


class _ColorTarget:
    """Record mask color mutations at the CuteCanvas presentation boundary."""

    def __init__(self) -> None:
        """Initialize an empty mutation history."""

        self.colors: list[tuple[UUID, QColor]] = []

    def set_mask_properties(self, mask_id: UUID, *, color: QColor) -> bool:
        """Record one accepted mask presentation color."""

        self.colors.append((mask_id, QColor(color)))
        return True


def test_canvas_hover_highlights_and_restores_mask_without_selecting() -> None:
    """Transient emphasis should restore the deterministic regional palette."""

    workflow = WorkflowState()
    image_id = uuid4()
    first_mask_id = uuid4()
    second_mask_id = uuid4()
    collection = workflow.canvas.ensure_regional_mask_collection(("Region", "masks"))
    collection.add_region(image_id, mask_id=first_mask_id)
    collection.add_region(image_id, mask_id=second_mask_id)
    collection.select(collection.entries[0].region_id)
    target = _ColorTarget()
    presenter = RegionalCanvasHoverPresenter(
        workflow=lambda: workflow,
        color_target=target,
    )

    presenter.show(("Region", "masks"), 1)
    presenter.clear()

    assert target.colors[0] == (second_mask_id, region_color(1, 2).lighter(135))
    assert target.colors[1] == (second_mask_id, region_color(1, 2))
    assert collection.selected_region_id == collection.entries[0].region_id
