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

"""Define the runtime arrangement of normal Input canvas tools."""

from __future__ import annotations

from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    InputCanvasToolId,
)
from substitute.presentation.canvas.tools import (
    CanvasToolGroupSlot,
    CanvasToolLayout,
    create_canvas_tool_layout,
)


def create_input_canvas_tool_layout() -> CanvasToolLayout:
    """Create the current product layout for the Input tool strip."""

    return create_canvas_tool_layout(
        (
            _single("input.slot.navigation", InputCanvasToolId.PAN_ZOOM),
            _single("input.slot.move", InputCanvasToolId.MOVE),
            _single("input.slot.brush", InputCanvasToolId.BRUSH),
            _single("input.slot.eraser", InputCanvasToolId.ERASER),
            CanvasToolGroupSlot(
                slot_id="input.slot.selection_shapes",
                tool_ids=(
                    InputCanvasToolId.SELECT_RECTANGLE,
                    InputCanvasToolId.SELECT_ELLIPSE,
                    InputCanvasToolId.SELECT_LASSO,
                ),
                selected_tool_id=InputCanvasToolId.SELECT_RECTANGLE,
            ),
            _single("input.slot.smart_select", InputCanvasToolId.SMART_SELECT),
            CanvasToolGroupSlot(
                slot_id="input.slot.mask_shapes",
                tool_ids=(
                    InputCanvasToolId.MASK_RECTANGLE,
                    InputCanvasToolId.MASK_ELLIPSE,
                    InputCanvasToolId.MASK_LASSO,
                ),
                selected_tool_id=InputCanvasToolId.MASK_RECTANGLE,
            ),
            _single("input.slot.smart_mask", InputCanvasToolId.SMART_MASK),
            CanvasToolGroupSlot(
                slot_id="input.slot.transform",
                tool_ids=(
                    InputCanvasToolId.TRANSFORM_LAYER,
                    InputCanvasToolId.SHARED_EDGE_RESIZE,
                ),
                selected_tool_id=InputCanvasToolId.TRANSFORM_LAYER,
            ),
        )
    )


def _single(
    slot_id: str,
    tool_id: str,
) -> CanvasToolGroupSlot:
    """Build one singleton slot with the same persistence contract as groups."""

    return CanvasToolGroupSlot(
        slot_id=slot_id,
        tool_ids=(tool_id,),
        selected_tool_id=tool_id,
    )


__all__ = ["create_input_canvas_tool_layout"]
