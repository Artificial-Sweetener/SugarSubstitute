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

"""Project authored Input tool context for non-workflow-focused tests."""

from __future__ import annotations

from typing import Protocol

from substitute.domain.workflow import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.input.input_canvas_tool_context_projection import (
    InputCanvasToolContextProjection,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)

_AUTHORED_PROFILE = InputCanvasInteractionProfile(
    frozenset({InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE})
)


class InputCanvasToolSnapshotPort(Protocol):
    """Expose a detached document tool snapshot to the test projection."""

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return current document readiness facts."""


def project_authored_input_tool_context(
    controller: InputCanvasToolController,
    document_context: InputCanvasToolSnapshotPort,
    *_args: object,
) -> None:
    """Apply authored applicability around tests focused on other tool behavior."""

    context = InputCanvasToolContextProjection.project(
        document_context.snapshot,
        _AUTHORED_PROFILE,
    )
    controller.palette.set_context(context)
    controller.reconcile_context_change(preserve_held_tool=True)


__all__ = ["project_authored_input_tool_context"]
