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

"""Define the built-in Input canvas contributions for the runtime tool system."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationText
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.presentation.canvas.tools import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolRuntime,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon

INPUT_CANVAS_CONTEXT = "canvas.input"
INPUT_CANVAS_CONTEXT_TAGS = frozenset({INPUT_CANVAS_CONTEXT})
INPUT_IMAGE_CAPABILITY = "input.image"
ACTIVE_MASK_CAPABILITY = "input.active_mask"
SMART_SELECT_CAPABILITY = "input.smart_select"


class InputCanvasToolId:
    """Own stable product identities for built-in Input canvas tools."""

    MOVE = "input.move"
    MASK_RECTANGLE = "input.mask.rectangle"
    MASK_ELLIPSE = "input.mask.ellipse"
    MASK_LASSO = "input.mask.lasso"
    SMART_SELECT = "input.mask.smart_select"
    BRUSH = "input.mask.brush"
    PAN_ZOOM = "input.pan_zoom"


def create_input_canvas_tool_system() -> CanvasToolRuntime:
    """Create the Input runtime with its built-in mode contributions."""

    runtime = CanvasToolRuntime()
    runtime.register_modes(
        (
            _mode(
                InputCanvasToolId.MOVE,
                app_text("Move"),
                AppIcon.ARROW_MOVE_20_REGULAR,
                order=100,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
            ),
            _mode(
                InputCanvasToolId.MASK_RECTANGLE,
                app_text("Rectangle Mask"),
                AppIcon.RECTANGLE_LANDSCAPE_20_REGULAR,
                order=200,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
            ),
            _mode(
                InputCanvasToolId.MASK_ELLIPSE,
                app_text("Ellipse Mask"),
                AppIcon.CIRCLE_20_REGULAR,
                order=300,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
            ),
            _mode(
                InputCanvasToolId.MASK_LASSO,
                app_text("Lasso Mask"),
                AppIcon.LASSO_20_REGULAR,
                order=400,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
            ),
            _mode(
                InputCanvasToolId.SMART_SELECT,
                app_text("Smart Select"),
                AppIcon.SELECT_OBJECT_20_REGULAR,
                order=500,
                required_capabilities={
                    ACTIVE_MASK_CAPABILITY,
                    SMART_SELECT_CAPABILITY,
                },
            ),
            _mode(
                InputCanvasToolId.BRUSH,
                app_text("Brush"),
                AppIcon.PAINT_BRUSH_20_REGULAR,
                order=600,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
            ),
            _mode(
                InputCanvasToolId.PAN_ZOOM,
                app_text("Pan & Zoom"),
                AppIcon.HAND_LEFT_20_REGULAR,
                section="navigation",
                order=700,
                required_capabilities={INPUT_IMAGE_CAPABILITY},
            ),
        )
    )
    return runtime


def _mode(
    tool_id: str,
    label: ApplicationText,
    icon: AppIcon,
    *,
    order: int,
    required_capabilities: set[str],
    section: str = "mask",
) -> CanvasToolContribution:
    """Build one persistent Input tool contribution with common context policy."""

    return CanvasToolContribution(
        tool_id=tool_id,
        label=label,
        icon=icon,
        kind=CanvasToolKind.MODE,
        section=section,
        order=order,
        required_context_tags=INPUT_CANVAS_CONTEXT_TAGS,
        required_capabilities=frozenset(required_capabilities),
    )


__all__ = [
    "ACTIVE_MASK_CAPABILITY",
    "INPUT_CANVAS_CONTEXT_TAGS",
    "INPUT_IMAGE_CAPABILITY",
    "SMART_SELECT_CAPABILITY",
    "InputCanvasToolId",
    "create_input_canvas_tool_system",
]
