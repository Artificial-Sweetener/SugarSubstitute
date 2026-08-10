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

"""Coordinate workflow-aware Input tool-context projection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from substitute.domain.workflow import WorkflowState
from substitute.domain.workflow.input_canvas_interaction_profile import (
    InputCanvasInteractionProfile,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.input.input_canvas_tool_context_projection import (
    InputCanvasToolContextProjection,
)
from substitute.presentation.canvas.tools import CanvasToolContext, CanvasToolPalette


class InputCanvasDocumentToolContextPort(Protocol):
    """Expose transient document facts used by Input tool projection."""

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return the latest detached document capability snapshot."""


class InputCanvasToolActivationPort(Protocol):
    """Reconcile native activation after projected tool state changes."""

    def reconcile_context_change(self, *, preserve_held_tool: bool) -> None:
        """Recover or restore the active tool under the new context."""


class InputCanvasToolProfileController:
    """Own the live projection of workflow and document tool semantics."""

    def __init__(
        self,
        *,
        document_context: InputCanvasDocumentToolContextPort,
        active_workflow: Callable[[], WorkflowState | None],
        interaction_profile: Callable[
            [WorkflowState | None, UUID | None], InputCanvasInteractionProfile
        ],
        palette: CanvasToolPalette,
        activation: InputCanvasToolActivationPort,
    ) -> None:
        """Capture semantic providers and the generic palette projection target."""

        self._document_context = document_context
        self._active_workflow = active_workflow
        self._interaction_profile = interaction_profile
        self.palette = palette
        self._activation = activation
        self._profile: InputCanvasInteractionProfile | None = None
        self._profile_workflow: WorkflowState | None = None
        self._profile_image_id: UUID | None = None
        self._context: CanvasToolContext | None = None
        self._closed = False

    def refresh_document_context(self, *_args: object) -> bool:
        """Reproject transient readiness while reusing unchanged workflow semantics."""

        return self._refresh(force_profile=False)

    def refresh_workflow_profile(self, *_args: object) -> bool:
        """Recompute applicability after an authoritative workflow projection."""

        return self._refresh(force_profile=True)

    def close(self, *_args: object) -> None:
        """Reject queued refreshes after the owning Input surface is torn down."""

        self._closed = True

    def _refresh(self, *, force_profile: bool) -> bool:
        """Publish only changed context derived from current authoritative state."""

        if self._closed:
            return False

        snapshot = self._document_context.snapshot
        workflow = self._active_workflow()
        profile = self._profile
        if (
            force_profile
            or profile is None
            or workflow is not self._profile_workflow
            or snapshot.image_id != self._profile_image_id
        ):
            profile = self._interaction_profile(workflow, snapshot.image_id)
        context = InputCanvasToolContextProjection.project(snapshot, profile)
        if context == self._context:
            self._profile = profile
            self._profile_workflow = workflow
            self._profile_image_id = snapshot.image_id
            return False
        applicability_changed = self._profile is not None and profile != self._profile
        self._profile = profile
        self._profile_workflow = workflow
        self._profile_image_id = snapshot.image_id
        self._context = context
        self.palette.set_context(context)
        self._activation.reconcile_context_change(
            preserve_held_tool=not applicability_changed
        )
        return True


__all__ = [
    "InputCanvasDocumentToolContextPort",
    "InputCanvasToolActivationPort",
    "InputCanvasToolProfileController",
]
