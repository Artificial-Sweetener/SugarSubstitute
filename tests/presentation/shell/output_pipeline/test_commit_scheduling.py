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

"""Verify final Output legacy adaptation and registered projection scheduling."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


from substitute.application.ports import OutputImageUpdate
from substitute.application.workflows.output_canvas_state_service import (
    OutputProjectionSchedulingIntent,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
)
from substitute.presentation.shell.output_image_pipeline import OutputImagePipeline


from tests.presentation.shell.output_pipeline.support import (
    PreparationDispatcherSpy,
    CommitQueueSpy,
    ProjectionCoordinatorSpy,
    noop_project_workflow,
)


def test_pipeline_legacy_submit_preserves_explicit_fallback_metadata() -> None:
    """Explicit non-live submission should retain restore/import fallback behavior."""

    dispatcher = PreparationDispatcherSpy()

    pipeline = OutputImagePipeline(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf",
            workflows={"wf": object()},
            get_workflow=lambda _workflow_id: SimpleNamespace(metadata={}),
        ),
        canvas_io_service=SimpleNamespace(
            resolve_node_meta_title=lambda _node_data: "Cube.Output",
            resolve_workflow_label=lambda _metadata: "Workflow",
        ),
        output_commit_handler=SimpleNamespace(
            commit_prepared_output_image=lambda _prepared: None,
            handle_output_image_preparation_failed=lambda _failure: None,
        ),
        output_canvas_projection_coordinator=ProjectionCoordinatorSpy(),
        canvas_host=SimpleNamespace(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=CommitQueueSpy(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=noop_project_workflow,
            active_workflow_id=lambda: "wf",
            output_canvas_visible=lambda: True,
        ),
    )

    pipeline.submit_legacy_output_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={"save": {"_meta": {"title": "Cube.Output"}}},
            file_path=Path("E:/out/004.png"),
            node_id="save",
        )
    )

    request = dispatcher.submitted[0]
    assert request.live_event is None
    assert request.source_key == "wf:save"
    assert request.source_label == "Cube"


def test_pipeline_schedules_registered_output_projection_from_intent() -> None:
    """Direct registrations should hand active projection work to the scheduler."""

    projected: list[tuple[str, object]] = []

    def project(workflow_id: str, image_id: object = None) -> None:
        projected.append((workflow_id, image_id))

    pipeline = OutputImagePipeline(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf",
            workflows={"wf": object()},
            get_workflow=lambda _workflow_id: SimpleNamespace(metadata={}),
        ),
        canvas_io_service=SimpleNamespace(
            resolve_node_meta_title=lambda _node_data: "Cube.Output",
            resolve_workflow_label=lambda _metadata: "Workflow",
        ),
        output_commit_handler=SimpleNamespace(
            commit_prepared_output_image=lambda _prepared: None,
            handle_output_image_preparation_failed=lambda _failure: None,
        ),
        output_canvas_projection_coordinator=ProjectionCoordinatorSpy(),
        canvas_host=SimpleNamespace(),
        preparation_dispatcher=PreparationDispatcherSpy(),  # type: ignore[arg-type]
        commit_queue=CommitQueueSpy(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=project,
            active_workflow_id=lambda: "wf",
            output_canvas_visible=lambda: True,
        ),
    )
    image_id = uuid4()

    pipeline.schedule_output_projection(
        OutputProjectionSchedulingIntent(
            workflow_id="wf",
            registered_image_id=image_id,
            should_schedule=True,
        )
    )
    pipeline.schedule_output_projection(
        OutputProjectionSchedulingIntent(
            workflow_id="inactive",
            registered_image_id=None,
            should_schedule=False,
        )
    )

    pipeline.flush_visible_output_projection()

    assert projected == [("wf", image_id)]
