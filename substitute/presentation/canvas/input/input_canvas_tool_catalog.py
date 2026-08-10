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
from cutecanvas import CuteCanvas
from qfluentwidgets import FluentIcon  # type: ignore[import-untyped]

from substitute.presentation.canvas.tools import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolRuntime,
    CanvasToolSurface,
)
from substitute.presentation.resources.fluent_app_icon import AppIcon

INPUT_CANVAS_CONTEXT = "canvas.input"
INPUT_CANVAS_CONTEXT_TAGS = frozenset({INPUT_CANVAS_CONTEXT})
INPUT_RASTER_ANALYSIS_CONTEXT = "canvas.input.raster_analysis"
INPUT_IMAGE_CAPABILITY = "input.image"
ACTIVE_MASK_CAPABILITY = "input.active_mask"
LAYER_TRANSFORM_CAPABILITY = "input.active_mask.transform"
SMART_SEGMENTATION_CAPABILITY = "input.smart_segmentation"
PIXEL_SELECTION_CAPABILITY = "input.pixel_selection"
SELECTION_TRANSFORM_CAPABILITY = "input.pixel_selection.transform"
SELECTION_CLEAR_CAPABILITY = "input.pixel_selection.clear"
BRUSH_OPTIONS_ID = "input.options.brush"


class InputCanvasToolId:
    """Own stable product identities for built-in Input canvas tools."""

    MOVE = "input.move"
    SHARED_EDGE_RESIZE = "input.layer.shared_edge_resize"
    TRANSFORM_SELECTION = "input.selection.transform"
    TRANSFORM_LAYER = "input.layer.transform"
    CLEAR_SELECTION_PIXELS = "input.selection.clear_pixels"
    DESELECT = "input.selection.deselect"
    SELECT_RECTANGLE = "input.selection.rectangle"
    SELECT_ELLIPSE = "input.selection.ellipse"
    SELECT_LASSO = "input.selection.lasso"
    MASK_RECTANGLE = "input.mask.rectangle"
    MASK_ELLIPSE = "input.mask.ellipse"
    MASK_LASSO = "input.mask.lasso"
    SMART_SELECT = "input.selection.smart_select"
    SMART_MASK = "input.mask.smart_mask"
    BRUSH = "input.mask.brush"
    ERASER = "input.mask.eraser"
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
                operation_id=CuteCanvas.CONTROL_MODE_MOVE,
            ),
            _mode(
                InputCanvasToolId.SHARED_EDGE_RESIZE,
                app_text("Resize shared edges"),
                AppIcon.ARROW_AUTOFIT_WIDTH_20_REGULAR,
                order=125,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_SHARED_EDGE_RESIZE,
            ),
            _mode(
                InputCanvasToolId.TRANSFORM_SELECTION,
                app_text("Transform"),
                AppIcon.SELECT_OBJECT_SKEW_20_REGULAR,
                section="selection",
                order=100,
                required_capabilities={
                    INPUT_IMAGE_CAPABILITY,
                    PIXEL_SELECTION_CAPABILITY,
                    SELECTION_TRANSFORM_CAPABILITY,
                },
                operation_id=CuteCanvas.CONTROL_MODE_TRANSFORM,
                surfaces={CanvasToolSurface.CONTEXTUAL_TOOLBAR},
            ),
            _mode(
                InputCanvasToolId.TRANSFORM_LAYER,
                app_text("Transform"),
                AppIcon.SELECT_OBJECT_SKEW_20_REGULAR,
                order=150,
                required_capabilities={
                    ACTIVE_MASK_CAPABILITY,
                    LAYER_TRANSFORM_CAPABILITY,
                },
                operation_id=CuteCanvas.CONTROL_MODE_TRANSFORM,
            ),
            _mode(
                InputCanvasToolId.SELECT_RECTANGLE,
                app_text("Rectangle selection"),
                AppIcon.SELECT_OBJECT_20_REGULAR,
                section="selection",
                order=200,
                required_capabilities={INPUT_IMAGE_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_SELECT_RECTANGLE,
            ),
            _mode(
                InputCanvasToolId.SELECT_ELLIPSE,
                app_text("Ellipse selection"),
                AppIcon.SELECT_ELLIPSE_20_REGULAR,
                section="selection",
                order=300,
                required_capabilities={INPUT_IMAGE_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_SELECT_ELLIPSE,
            ),
            _mode(
                InputCanvasToolId.SELECT_LASSO,
                app_text("Lasso selection"),
                AppIcon.LASSO_20_REGULAR,
                section="selection",
                order=400,
                required_capabilities={INPUT_IMAGE_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_SELECT_LASSO,
            ),
            _mode(
                InputCanvasToolId.SMART_SELECT,
                app_text("Smart Select"),
                AppIcon.SMART_SELECT_20_REGULAR,
                section="selection",
                order=450,
                required_capabilities={
                    INPUT_IMAGE_CAPABILITY,
                    SMART_SEGMENTATION_CAPABILITY,
                },
                required_context_tags={INPUT_RASTER_ANALYSIS_CONTEXT},
                operation_id=CuteCanvas.CONTROL_MODE_SMART_SELECT,
            ),
            _mode(
                InputCanvasToolId.MASK_RECTANGLE,
                app_text("Rectangle Mask"),
                AppIcon.MASK_RECTANGLE_20_REGULAR,
                order=500,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_MASK_RECTANGLE,
            ),
            _mode(
                InputCanvasToolId.MASK_ELLIPSE,
                app_text("Ellipse Mask"),
                AppIcon.MASK_ELLIPSE_20_REGULAR,
                order=600,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_MASK_ELLIPSE,
            ),
            _mode(
                InputCanvasToolId.MASK_LASSO,
                app_text("Lasso Mask"),
                AppIcon.MASK_LASSO_20_REGULAR,
                order=700,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_MASK_LASSO,
            ),
            _mode(
                InputCanvasToolId.SMART_MASK,
                app_text("Smart Mask"),
                AppIcon.SMART_MASK_20_REGULAR,
                order=800,
                required_capabilities={
                    ACTIVE_MASK_CAPABILITY,
                    SMART_SEGMENTATION_CAPABILITY,
                },
                required_context_tags={INPUT_RASTER_ANALYSIS_CONTEXT},
                operation_id=CuteCanvas.CONTROL_MODE_SMART_MASK,
            ),
            _mode(
                InputCanvasToolId.BRUSH,
                app_text("Brush"),
                AppIcon.PAINT_BRUSH_20_REGULAR,
                order=900,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_DRAW_BRUSH,
                options_id=BRUSH_OPTIONS_ID,
            ),
            _mode(
                InputCanvasToolId.ERASER,
                app_text("Eraser"),
                AppIcon.ERASER_20_REGULAR,
                order=950,
                required_capabilities={ACTIVE_MASK_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_ERASER,
                options_id=BRUSH_OPTIONS_ID,
            ),
            _mode(
                InputCanvasToolId.PAN_ZOOM,
                app_text("Pan & Zoom"),
                AppIcon.HAND_LEFT_20_REGULAR,
                section="navigation",
                order=1000,
                required_capabilities={INPUT_IMAGE_CAPABILITY},
                operation_id=CuteCanvas.CONTROL_MODE_PANZOOM,
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
    required_context_tags: set[str] | None = None,
    section: str = "mask",
    operation_id: str,
    options_id: str | None = None,
    surfaces: set[CanvasToolSurface] | None = None,
) -> CanvasToolContribution:
    """Build one persistent Input tool contribution with common context policy."""

    return CanvasToolContribution(
        tool_id=tool_id,
        label=label,
        icon=icon,
        kind=CanvasToolKind.MODE,
        section=section,
        order=order,
        required_context_tags=INPUT_CANVAS_CONTEXT_TAGS.union(
            required_context_tags or ()
        ),
        required_capabilities=frozenset(required_capabilities),
        document_operation_id=operation_id,
        options_id=options_id,
        surfaces=(
            frozenset({CanvasToolSurface.TOOL_STRIP})
            if surfaces is None
            else frozenset(surfaces)
        ),
    )


def deselect_contribution() -> CanvasToolContribution:
    """Return the selection-owned one-shot Deselect contribution."""
    return CanvasToolContribution(
        tool_id=InputCanvasToolId.DESELECT,
        label=app_text("Deselect"),
        icon=FluentIcon.CLEAR_SELECTION,
        kind=CanvasToolKind.ACTION,
        section="selection",
        order=300,
        required_context_tags=INPUT_CANVAS_CONTEXT_TAGS,
        required_capabilities=frozenset({PIXEL_SELECTION_CAPABILITY}),
        surfaces=frozenset({CanvasToolSurface.CONTEXTUAL_TOOLBAR}),
    )


def clear_selection_pixels_contribution() -> CanvasToolContribution:
    """Return the selection-owned one-shot pixel Clear contribution."""
    return CanvasToolContribution(
        tool_id=InputCanvasToolId.CLEAR_SELECTION_PIXELS,
        label=app_text("Clear"),
        icon=AppIcon.ERASER_20_REGULAR,
        kind=CanvasToolKind.ACTION,
        section="selection",
        order=200,
        required_context_tags=INPUT_CANVAS_CONTEXT_TAGS,
        required_capabilities=frozenset(
            {PIXEL_SELECTION_CAPABILITY, SELECTION_CLEAR_CAPABILITY}
        ),
        surfaces=frozenset({CanvasToolSurface.CONTEXTUAL_TOOLBAR}),
    )


__all__ = [
    "ACTIVE_MASK_CAPABILITY",
    "BRUSH_OPTIONS_ID",
    "INPUT_CANVAS_CONTEXT_TAGS",
    "INPUT_IMAGE_CAPABILITY",
    "INPUT_RASTER_ANALYSIS_CONTEXT",
    "LAYER_TRANSFORM_CAPABILITY",
    "PIXEL_SELECTION_CAPABILITY",
    "SELECTION_CLEAR_CAPABILITY",
    "SELECTION_TRANSFORM_CAPABILITY",
    "SMART_SEGMENTATION_CAPABILITY",
    "InputCanvasToolId",
    "create_input_canvas_tool_system",
    "clear_selection_pixels_contribution",
    "deselect_contribution",
]
