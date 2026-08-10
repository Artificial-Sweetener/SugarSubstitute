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

"""Verify Input tool projection keeps applicability separate from readiness."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from substitute.domain.workflow import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
    WorkflowState,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    INPUT_RASTER_ANALYSIS_CONTEXT,
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.input.input_canvas_tool_context_projection import (
    InputCanvasToolContextProjection,
)
from substitute.presentation.canvas.input.input_canvas_tool_profile_controller import (
    InputCanvasToolProfileController,
)


@dataclass
class _DocumentContext:
    """Expose mutable document readiness to the profile controller."""

    image_id: UUID | None = None
    has_active_mask: bool = False
    sam_ready: bool = False

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return the current detached readiness snapshot."""

        return InputCanvasToolContextSnapshot(
            image_id=self.image_id,
            has_active_mask=self.has_active_mask,
            smart_segmentation_ready=self.sam_ready,
            has_pixel_selection=False,
            selection_transform_available=False,
            layer_transform_available=False,
            selection_clear_available=False,
        )


class _ActivationReconciler:
    """Record whether applicability changes preserve held tools."""

    def __init__(self) -> None:
        """Initialize an empty reconciliation history."""

        self.preserve_held: list[bool] = []

    def reconcile_context_change(self, *, preserve_held_tool: bool) -> None:
        """Record one requested activation reconciliation."""

        self.preserve_held.append(preserve_held_tool)


def test_synthetic_profile_removes_smart_tools_from_the_palette() -> None:
    """Synthetic applicability should structurally exclude both smart tools."""

    document = _DocumentContext(image_id=uuid4(), has_active_mask=True, sam_ready=True)
    controller = _controller(document, _synthetic_profile())

    assert controller.refresh_workflow_profile()

    assert controller.palette.presentation_for(InputCanvasToolId.SMART_SELECT) is None
    assert controller.palette.presentation_for(InputCanvasToolId.SMART_MASK) is None
    edge_resize = controller.palette.presentation_for(
        InputCanvasToolId.SHARED_EDGE_RESIZE
    )
    assert edge_resize is not None and edge_resize.enabled


def test_authored_profile_keeps_smart_tools_visible_while_readiness_disables() -> None:
    """Authored raster applicability should not be conflated with SAM readiness."""

    document = _DocumentContext(image_id=uuid4())
    controller = _controller(document, _authored_profile())

    assert controller.refresh_workflow_profile()
    smart_select = controller.palette.presentation_for(InputCanvasToolId.SMART_SELECT)
    smart_mask = controller.palette.presentation_for(InputCanvasToolId.SMART_MASK)
    assert smart_select is not None and not smart_select.enabled
    assert smart_mask is not None and not smart_mask.enabled

    document.sam_ready = True
    assert controller.refresh_document_context()
    smart_select = controller.palette.presentation_for(InputCanvasToolId.SMART_SELECT)
    smart_mask = controller.palette.presentation_for(InputCanvasToolId.SMART_MASK)
    assert smart_select is not None and smart_select.enabled
    assert smart_mask is not None and not smart_mask.enabled

    document.has_active_mask = True
    assert controller.refresh_document_context()
    smart_mask = controller.palette.presentation_for(InputCanvasToolId.SMART_MASK)
    assert smart_mask is not None and smart_mask.enabled
    edge_resize = controller.palette.presentation_for(
        InputCanvasToolId.SHARED_EDGE_RESIZE
    )
    assert edge_resize is not None and edge_resize.enabled


def test_profile_transition_marks_only_applicability_change_as_non_transient() -> None:
    """Readiness may restore held tools while workflow applicability may not."""

    document = _DocumentContext(image_id=uuid4())
    workflow = WorkflowState()
    current_profile = [_authored_profile()]
    runtime = create_input_canvas_tool_system()
    reconciler = _ActivationReconciler()
    controller = InputCanvasToolProfileController(
        document_context=document,
        active_workflow=lambda: workflow,
        interaction_profile=lambda _workflow, _image_id: current_profile[0],
        palette=runtime.palette,
        activation=reconciler,
    )

    assert controller.refresh_workflow_profile()
    document.sam_ready = True
    assert controller.refresh_document_context()
    current_profile[0] = _synthetic_profile()
    assert controller.refresh_workflow_profile()

    assert reconciler.preserve_held == [True, True, False]


def test_context_projection_uses_a_semantic_raster_tag_only_for_authored_source() -> (
    None
):
    """The generic context should receive presentation tags from typed semantics."""

    snapshot = _DocumentContext(image_id=uuid4()).snapshot

    authored = InputCanvasToolContextProjection.project(snapshot, _authored_profile())
    synthetic = InputCanvasToolContextProjection.project(snapshot, _synthetic_profile())

    assert INPUT_RASTER_ANALYSIS_CONTEXT in authored.tags
    assert INPUT_RASTER_ANALYSIS_CONTEXT not in synthetic.tags


def _controller(
    document: _DocumentContext,
    profile: InputCanvasInteractionProfile,
) -> InputCanvasToolProfileController:
    """Build one production palette projection around a fixed workflow profile."""

    workflow = WorkflowState()
    runtime = create_input_canvas_tool_system()
    return InputCanvasToolProfileController(
        document_context=document,
        active_workflow=lambda: workflow,
        interaction_profile=lambda _workflow, _image_id: profile,
        palette=runtime.palette,
        activation=_ActivationReconciler(),
    )


def _authored_profile() -> InputCanvasInteractionProfile:
    """Return a profile backed by an authored raster analysis source."""

    return InputCanvasInteractionProfile(
        frozenset({InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE})
    )


def _synthetic_profile() -> InputCanvasInteractionProfile:
    """Return a profile with no raster analysis source."""

    return InputCanvasInteractionProfile()
