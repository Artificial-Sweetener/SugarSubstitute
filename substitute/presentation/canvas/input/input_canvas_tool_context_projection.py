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

"""Project Input workflow applicability and document readiness into tool state."""

from __future__ import annotations

from sugarsubstitute_shared.presentation.localization import app_text

from substitute.domain.workflow.input_canvas_interaction_profile import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    ACTIVE_MASK_CAPABILITY,
    INPUT_CANVAS_CONTEXT_TAGS,
    INPUT_IMAGE_CAPABILITY,
    INPUT_RASTER_ANALYSIS_CONTEXT,
    LAYER_TRANSFORM_CAPABILITY,
    PIXEL_SELECTION_CAPABILITY,
    SELECTION_CLEAR_CAPABILITY,
    SELECTION_TRANSFORM_CAPABILITY,
    SMART_SEGMENTATION_CAPABILITY,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.tools import CanvasToolContext


class InputCanvasToolContextProjection:
    """Translate typed Input semantics into the reusable tool-system context."""

    @staticmethod
    def project(
        snapshot: InputCanvasToolContextSnapshot,
        profile: InputCanvasInteractionProfile,
    ) -> CanvasToolContext:
        """Combine workflow applicability with transient document capabilities."""

        tags = set(INPUT_CANVAS_CONTEXT_TAGS)
        if profile.supports(InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE):
            tags.add(INPUT_RASTER_ANALYSIS_CONTEXT)
        capabilities: set[str] = set()
        if snapshot.image_id is not None:
            capabilities.add(INPUT_IMAGE_CAPABILITY)
        if snapshot.has_active_mask:
            capabilities.add(ACTIVE_MASK_CAPABILITY)
            if snapshot.layer_transform_available:
                capabilities.add(LAYER_TRANSFORM_CAPABILITY)
        if snapshot.smart_segmentation_ready:
            capabilities.add(SMART_SEGMENTATION_CAPABILITY)
        if snapshot.has_pixel_selection:
            capabilities.add(PIXEL_SELECTION_CAPABILITY)
            if snapshot.selection_transform_available:
                capabilities.add(SELECTION_TRANSFORM_CAPABILITY)
            if snapshot.selection_clear_available:
                capabilities.add(SELECTION_CLEAR_CAPABILITY)
        return CanvasToolContext(
            tags=frozenset(tags),
            capabilities=frozenset(capabilities),
            capability_denials=(
                (LAYER_TRANSFORM_CAPABILITY, app_text("Nothing to transform!")),
            ),
        )


__all__ = ["InputCanvasToolContextProjection"]
