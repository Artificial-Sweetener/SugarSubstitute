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

"""Expose prompt-editor overlay presentation owners."""

from __future__ import annotations

from .autocomplete_panel import (
    PromptAutocompleteActivationIntent,
    PromptAutocompleteLoraActivationSignal,
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
    PromptAutocompleteOverlay,
    PromptAutocompletePanel,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRow,
    PromptAutocompleteRowRenderState,
    format_prompt_autocomplete_popularity,
)
from .autocomplete_presenter import (
    PromptAutocompleteLoraWallFactory,
    PromptAutocompletePanelFactory,
    PromptAutocompletePanelPresenter,
    PromptAutocompletePresentationEditor,
    PromptAutocompletePresenter,
)
from .chip_painter import PromptChipPainter, PromptChipPaintStyle
from .chip_visuals import PromptChipVisual, PromptChipVisualBuilder
from .lora_wall import (
    LORA_WALL_PROFILE,
    PromptLoraActivationIntent,
    PromptLoraPickerPopup,
    PromptLoraWallItemRenderState,
    PromptLoraWallOverlay,
    PromptLoraWallRenderState,
    PromptLoraWallView,
    lora_item_aspect_ratio,
    model_picker_items_for_loras,
    show_lora_picker_popup,
    wall_items_for_loras,
)
from .reorder_drag_proxy import (
    PromptReorderDragProxy,
    PromptReorderDragProxyPlacement,
    PromptReorderDragProxyRenderState,
    PromptReorderDragProxyWidget,
)
from .reorder_autoscroll import (
    PromptReorderAutoscrollContext,
    PromptReorderAutoscrollController,
)
from .reorder_animation_presenter import PromptReorderAnimationPresenter
from .reorder_gesture_controller import (
    PromptReorderDragProxyPlacementContext,
    PromptReorderDragProxyPlacementController,
    PromptReorderGestureController,
    PromptReorderGestureSnapshot,
    PromptReorderGestureStateView,
)
from .reorder_overlay import (
    PromptReorderAutoscrollFactory,
    PromptReorderCancelIntent,
    PromptReorderCommitIntent,
    PromptReorderDragIntent,
    PromptReorderDragPhase,
    PromptReorderDragProxyStateFactory,
    PromptReorderLayoutPolicy,
    PromptReorderOverlay,
    PromptReorderOverlayRenderState,
    PromptReorderViewFactory,
    SegmentReorderOverlay,
)
from .reorder_view import (
    PromptReorderChipPaintState,
    PromptReorderLandingPreviewPaintState,
    PromptReorderMarkerPaintState,
    PromptReorderView,
    PromptReorderViewRenderState,
    PromptReorderVisualStyle,
)
from .token_weight_controls import (
    PromptTokenWeightExactEditHost,
    PromptTokenWeightControls,
    PromptTokenWeightControlsSurface,
    PromptTokenWeightGestureControllerFactory,
    PromptTokenWeightViewFactory,
)
from .token_weight_geometry import (
    PromptTokenWeightControlGeometry,
    PromptTokenWeightGeometry,
    PromptTokenWeightGeometrySnapshot,
    PromptTokenWeightGeometrySurface,
    PromptTokenWeightProjectionSnapshot,
)
from .token_weight_gestures import (
    PromptTokenWeightControl,
    PromptTokenWeightGestureController,
    PromptTokenWeightGestureSnapshot,
    PromptTokenWeightStepIntent,
    PromptTokenWeightWheelStepIntent,
)
from .token_weight_view import (
    PromptTokenWeightControlPaintState,
    PromptTokenWeightPreviewPaintState,
    PromptTokenWeightView,
    PromptTokenWeightViewRenderState,
)

__all__ = [
    "PromptAutocompleteActivationIntent",
    "PromptAutocompleteLoraActivationSignal",
    "PromptAutocompleteLoraWall",
    "PromptAutocompleteLoraWallFactory",
    "PromptAutocompleteLoraWallRenderState",
    "PromptAutocompleteOverlay",
    "PromptAutocompletePanel",
    "PromptAutocompletePanelFactory",
    "PromptAutocompletePanelPresenter",
    "PromptAutocompletePanelRenderState",
    "PromptAutocompletePresentationEditor",
    "PromptAutocompletePresenter",
    "PromptAutocompleteRow",
    "PromptAutocompleteRowRenderState",
    "PromptChipPainter",
    "PromptChipPaintStyle",
    "PromptChipVisual",
    "PromptChipVisualBuilder",
    "LORA_WALL_PROFILE",
    "PromptLoraActivationIntent",
    "PromptLoraPickerPopup",
    "PromptLoraWallItemRenderState",
    "PromptLoraWallOverlay",
    "PromptLoraWallRenderState",
    "PromptLoraWallView",
    "PromptReorderCancelIntent",
    "PromptReorderChipPaintState",
    "PromptReorderCommitIntent",
    "PromptReorderAutoscrollFactory",
    "PromptReorderDragIntent",
    "PromptReorderDragPhase",
    "PromptReorderAutoscrollContext",
    "PromptReorderAutoscrollController",
    "PromptReorderAnimationPresenter",
    "PromptReorderDragProxy",
    "PromptReorderDragProxyPlacement",
    "PromptReorderDragProxyPlacementContext",
    "PromptReorderDragProxyPlacementController",
    "PromptReorderDragProxyRenderState",
    "PromptReorderDragProxyStateFactory",
    "PromptReorderDragProxyWidget",
    "PromptReorderGestureController",
    "PromptReorderGestureSnapshot",
    "PromptReorderGestureStateView",
    "PromptReorderLayoutPolicy",
    "PromptReorderOverlay",
    "PromptReorderOverlayRenderState",
    "PromptReorderViewFactory",
    "PromptReorderLandingPreviewPaintState",
    "PromptReorderMarkerPaintState",
    "PromptReorderView",
    "PromptReorderViewRenderState",
    "PromptReorderVisualStyle",
    "SegmentReorderOverlay",
    "PromptTokenWeightControls",
    "PromptTokenWeightControl",
    "PromptTokenWeightExactEditHost",
    "PromptTokenWeightControlsSurface",
    "PromptTokenWeightGestureControllerFactory",
    "PromptTokenWeightGestureController",
    "PromptTokenWeightGestureSnapshot",
    "PromptTokenWeightControlGeometry",
    "PromptTokenWeightControlPaintState",
    "PromptTokenWeightGeometry",
    "PromptTokenWeightGeometrySnapshot",
    "PromptTokenWeightGeometrySurface",
    "PromptTokenWeightPreviewPaintState",
    "PromptTokenWeightProjectionSnapshot",
    "PromptTokenWeightStepIntent",
    "PromptTokenWeightView",
    "PromptTokenWeightViewFactory",
    "PromptTokenWeightViewRenderState",
    "PromptTokenWeightWheelStepIntent",
    "format_prompt_autocomplete_popularity",
    "lora_item_aspect_ratio",
    "model_picker_items_for_loras",
    "show_lora_picker_popup",
    "wall_items_for_loras",
]
