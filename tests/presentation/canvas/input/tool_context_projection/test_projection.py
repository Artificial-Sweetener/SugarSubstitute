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

"""Verify typed interaction profiles project into palette context tags."""

from __future__ import annotations

from uuid import uuid4

from substitute.domain.workflow import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    INPUT_RASTER_ANALYSIS_CONTEXT,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.input.input_canvas_tool_context_projection import (
    InputCanvasToolContextProjection,
)


def test_context_projection_uses_semantic_raster_tag_only_for_authored_source() -> None:
    """Project the raster-analysis tag only from authored source semantics."""

    snapshot = InputCanvasToolContextSnapshot(
        image_id=uuid4(),
        has_active_mask=False,
        smart_segmentation_ready=False,
        has_pixel_selection=False,
        selection_transform_available=False,
        layer_transform_available=False,
        selection_clear_available=False,
        edit_session_active=False,
    )
    authored = InputCanvasToolContextProjection.project(
        snapshot,
        InputCanvasInteractionProfile(
            frozenset({InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE})
        ),
    )
    synthetic = InputCanvasToolContextProjection.project(
        snapshot,
        InputCanvasInteractionProfile(),
    )

    assert INPUT_RASTER_ANALYSIS_CONTEXT in authored.tags
    assert INPUT_RASTER_ANALYSIS_CONTEXT not in synthetic.tags
