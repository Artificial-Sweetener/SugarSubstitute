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

"""Verify Input-node interaction routes mask clicks by graph identity."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.domain.workflow import WorkflowCanvasState
from substitute.presentation.canvas.input.input_node_interaction_controller import (
    InputNodeInteractionController,
)
from substitute.presentation.regional.mask_editor_actions import (
    RegionalMaskActionOutcome,
)


def test_mask_click_activates_its_owning_image_and_mask() -> None:
    """Activate the graph-bound image and mask before focusing the Input route."""

    image_id = uuid4()
    mask_id = uuid4()
    active_images: list[UUID] = []
    active_masks: list[UUID] = []
    focused: list[str] = []
    workflow = _workflow(image_id=image_id, mask_id=mask_id)

    def set_active_input_image(
        _workflow_id: str,
        _workflow: object,
        value: UUID,
    ) -> bool:
        """Record active image activation."""

        active_images.append(value)
        return True

    def set_active_workflow_mask(
        _workflow_id: str,
        _workflow: object,
        value: UUID,
    ) -> bool:
        """Record active mask activation."""

        active_masks.append(value)
        return True

    def activate_input() -> bool:
        """Record route activation through the route-owner boundary."""

        focused.append("Input")
        workflow.canvas.active_canvas_route = "Input"
        return True

    controller = InputNodeInteractionController(
        active_workflow=lambda: cast(Any, workflow),
        active_workflow_id=lambda: "wf-a",
        workflow_input_canvas_service=cast(
            Any,
            SimpleNamespace(
                binding_for_mask=lambda *_args: SimpleNamespace(
                    section_key="CubeA",
                    surface_key="ImageNode",
                    association_key=("CubeA", "MaskNode"),
                ),
                bindings_for_image=lambda *_args: (),
            ),
        ),
        input_canvas_state_service=cast(
            Any,
            SimpleNamespace(
                set_active_input_image=set_active_input_image,
                set_active_workflow_mask=set_active_workflow_mask,
            ),
        ),
        materialize_image_selection=lambda *_args: True,
        apply_mask_selection=lambda *_args: True,
        handle_ordered_mask_action=lambda *_args: RegionalMaskActionOutcome(False),
        activate_input_canvas=activate_input,
        refresh_mask_pickers=lambda: None,
    )

    controller.handle_mask_clicked("CubeA", "MaskNode", "")

    assert active_images == [image_id]
    assert active_masks == [mask_id]
    assert focused == ["Input"]
    assert workflow.canvas.active_canvas_route == "Input"


def _workflow(*, image_id: UUID, mask_id: UUID) -> SimpleNamespace:
    """Build one workflow with graph-bound image and mask identities."""

    canvas = WorkflowCanvasState()
    canvas.bind_image("CubeA:ImageNode", image_id)
    canvas.bind_mask(("CubeA", "MaskNode"), mask_id, image_id)
    return SimpleNamespace(canvas=canvas, cubes={})
