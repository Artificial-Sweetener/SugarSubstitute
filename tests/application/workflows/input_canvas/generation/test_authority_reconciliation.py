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

"""Verify repair of persisted Input surfaces that lost graph authority."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from substitute.application.workflows.generation_input_image_selection_service import (
    GenerationInputImageSelection,
    GenerationInputImageSelectionService,
)
from substitute.application.workflows.input_canvas_authority_reconciliation_service import (
    InputCanvasAuthorityReconciliationService,
)
from substitute.application.workflows.input_canvas_plan_service import (
    InputCanvasPlanService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.canvas.input.input_generation_capture import (
    InputGenerationCapture,
)
from substitute.presentation.canvas.input.input_generation_snapshot_service import (
    InputGenerationSnapshotService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from tests.application.workflows.input_canvas.fakes import (
    _FakeInputCanvasStateService,
)


def test_reconciliation_drops_only_surfaces_rejected_by_graph_authority() -> None:
    """Legacy stale entries must be retired without disturbing valid surfaces."""

    valid_image_id = uuid4()
    stale_image_id = uuid4()
    stale_mask_id = uuid4()
    workflow = WorkflowState()
    workflow.canvas.bind_image("Valid:Image", valid_image_id)
    workflow.canvas.bind_image("Removed:Image", stale_image_id)
    workflow.canvas.bind_mask(("Removed", "Mask"), stale_mask_id, stale_image_id)
    canvas_state = _FakeInputCanvasStateService(
        image_id=valid_image_id,
        mask_id=stale_mask_id,
    )
    service = InputCanvasAuthorityReconciliationService(
        select_generation_images=lambda _workflow: GenerationInputImageSelection(
            (valid_image_id,),
            unresolved_input_keys=("Removed:Image",),
        ),
        input_canvas_state_service=canvas_state,
    )

    report = service.reconcile({"wf-a": workflow}, "wf-a")

    assert report.workflow_id == "wf-a"
    assert report.stale_input_keys == ("Removed:Image",)
    assert report.removed_input_keys == ("Removed:Image",)
    assert workflow.canvas.image_entry("Valid:Image") is not None
    assert workflow.canvas.image_entry("Removed:Image") is None
    assert workflow.canvas.mask_entry(("Removed", "Mask")) is None
    assert canvas_state.dropped_associations == [("Removed", "Mask")]


def test_reconciliation_of_missing_workflow_is_an_observable_noop() -> None:
    """A stale workflow route must not invoke graph selection or mutate state."""

    def unexpected_selection(_workflow: WorkflowState) -> GenerationInputImageSelection:
        """Reject graph inspection when the requested workflow is absent."""

        raise AssertionError("selection must not run")

    service = InputCanvasAuthorityReconciliationService(
        select_generation_images=unexpected_selection,
        input_canvas_state_service=_FakeInputCanvasStateService(
            image_id=uuid4(),
            mask_id=uuid4(),
        ),
    )

    report = service.reconcile({}, "missing")

    assert report.workflow_id == "missing"
    assert report.stale_input_keys == ()
    assert report.removed_input_keys == ()


def test_stale_surface_in_workflow_without_input_canvas_recovers_before_capture() -> (
    None
):
    """The reported no-canvas failure must become an empty generation capture."""

    stale_image_id = uuid4()
    workflow = WorkflowState()
    workflow.canvas.bind_image("Removed:Image", stale_image_id)
    workflows = {"wf-a": workflow}

    def unexpected_plan(*_args: object) -> object:
        """Reject plan construction for a workflow with no graph sections."""

        raise AssertionError("missing graph sections must not build plans")

    selector = GenerationInputImageSelectionService(
        input_canvas_plan_service=cast(
            InputCanvasPlanService,
            SimpleNamespace(build_plan=unexpected_plan),
        ),
        graph_section_service=WorkflowGraphSectionService(),
    )
    authority = InputCanvasAuthorityReconciliationService(
        select_generation_images=selector.select,
        input_canvas_state_service=_FakeInputCanvasStateService(
            image_id=stale_image_id,
            mask_id=uuid4(),
        ),
    )

    report = authority.reconcile(workflows, "wf-a")

    capture_requests: list[tuple[tuple[UUID, ...], tuple[UUID, ...]]] = []

    def capture_inputs(
        *,
        image_ids: tuple[UUID, ...],
        mask_ids: tuple[UUID, ...],
    ) -> InputGenerationCapture:
        """Record the post-recovery capture identities."""

        capture_requests.append((image_ids, mask_ids))
        return InputGenerationCapture(images={}, masks={})

    copy_materializer = SimpleNamespace(
        prepare_workflow=lambda **kwargs: copy.deepcopy(kwargs["workflow"])
    )
    snapshot_service = InputGenerationSnapshotService(
        capture_inputs=capture_inputs,
        select_generation_images=selector.select,
        image_materializer=copy_materializer,
        mask_materializer=copy_materializer,
    )
    prepared = snapshot_service.prepare_workflow(
        workflow_id="wf-a",
        workflow=workflow,
    )

    assert report.removed_input_keys == ("Removed:Image",)
    assert isinstance(prepared, WorkflowState)
    assert capture_requests == [((), ())]
