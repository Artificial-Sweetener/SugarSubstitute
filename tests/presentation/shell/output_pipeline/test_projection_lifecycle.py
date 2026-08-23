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

"""Verify final Output host projection lifecycle orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4


from substitute.application.workflows.output_canvas_state_service import (
    OutputProjectionSchedulingIntent,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    ProjectionReason,
)
from substitute.presentation.shell.output_image_pipeline import OutputImagePipeline


from tests.presentation.shell.output_pipeline.support import (
    SignalSpy,
    PreparationDispatcherSpy,
    CommitQueueSpy,
    ProjectionSchedulerSpy,
    ProjectionCoordinatorSpy,
    build_pipeline_shell_dependencies,
)


def test_pipeline_uses_host_activation_signal_for_output_projection() -> None:
    """Output projection should subscribe to host activation, not pivot internals."""

    scheduler = ProjectionSchedulerSpy()
    signal = SignalSpy()
    canvas_host = SimpleNamespace(canvas_activated=signal)

    OutputImagePipeline(
        **build_pipeline_shell_dependencies(),
        canvas_host=canvas_host,
        projection_scheduler=scheduler,  # type: ignore[arg-type]
    )
    signal.callbacks[0]("Input")
    signal.callbacks[0]("Output")

    assert len(signal.callbacks) == 1
    assert scheduler.requests == [("wf", ProjectionReason.WORKFLOW_ACTIVATED, None)]


def test_pipeline_visibility_uses_generic_host_visibility_api() -> None:
    """Output visibility should be read through the generic host surface."""

    calls: list[str] = []

    def is_canvas_visible(label: str) -> bool:
        """Capture the visibility label and report hidden Output canvas."""

        calls.append(label)
        return False

    pipeline = OutputImagePipeline(
        **build_pipeline_shell_dependencies(),
        canvas_host=SimpleNamespace(
            is_canvas_visible=is_canvas_visible,
        ),
        projection_scheduler=ProjectionSchedulerSpy(),  # type: ignore[arg-type]
    )

    assert pipeline._output_canvas_is_visible() is False
    assert calls == ["Output"]


def test_pipeline_projects_through_output_projection_coordinator() -> None:
    """Default projection scheduling should not use shell pass-through facades."""

    workflows = {"wf": object(), "inactive": object()}
    coordinator = ProjectionCoordinatorSpy()
    pipeline = OutputImagePipeline(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf",
            workflows=workflows,
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
        output_canvas_projection_coordinator=coordinator,
        canvas_host=SimpleNamespace(is_canvas_visible=lambda _label: True),
        preparation_dispatcher=PreparationDispatcherSpy(),  # type: ignore[arg-type]
        commit_queue=CommitQueueSpy(),  # type: ignore[arg-type]
    )
    image_id = uuid4()

    pipeline.schedule_user_selected_output_projection("wf")
    pipeline.schedule_user_selected_output_projection("inactive")
    pipeline.schedule_output_projection(
        OutputProjectionSchedulingIntent(
            workflow_id="wf",
            registered_image_id=image_id,
            should_schedule=True,
        )
    )
    pipeline.flush_visible_output_projection()

    assert coordinator.projected == [
        (workflows, "wf", None),
        (workflows, "wf", image_id),
    ]


def test_pipeline_discards_pending_projection_work_for_removed_workflow() -> None:
    """Workflow lifecycle cleanup should be delegated to the scheduler owner."""

    scheduler = ProjectionSchedulerSpy()
    pipeline = OutputImagePipeline(
        **build_pipeline_shell_dependencies(),
        canvas_host=SimpleNamespace(),
        projection_scheduler=scheduler,  # type: ignore[arg-type]
    )

    pipeline.remove_workflow("wf-closed")

    assert scheduler.discarded == ["wf-closed"]


def test_pipeline_rekeys_pending_projection_work_for_renamed_workflow() -> None:
    """Workflow rename should be delegated to the scheduler owner."""

    scheduler = ProjectionSchedulerSpy()
    pipeline = OutputImagePipeline(
        **build_pipeline_shell_dependencies(),
        canvas_host=SimpleNamespace(),
        projection_scheduler=scheduler,  # type: ignore[arg-type]
    )

    pipeline.rename_workflow("wf-old", "wf-new")

    assert scheduler.renamed == [("wf-old", "wf-new")]
