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

"""Verify strict final Output request identity and metadata construction."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.application.ports import OutputImageUpdate
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
)
from substitute.presentation.shell.output_image_pipeline import OutputImagePipeline


from tests.presentation.shell.output_pipeline.support import (
    PreparationDispatcherSpy,
    CommitQueueSpy,
    ProjectionCoordinatorSpy,
    TimingLookupStub,
    noop_project_workflow,
)


def test_pipeline_builds_strict_live_request_without_retaining_payload() -> None:
    """Live request construction should capture strict backend metadata only."""

    dispatcher = PreparationDispatcherSpy()

    def project(_workflow_id: str, _image_id: object = None) -> None:
        pass

    timing_lookup = TimingLookupStub()
    pipeline = OutputImagePipeline(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf",
            workflows={"wf": object()},
            get_workflow=lambda _workflow_id: SimpleNamespace(
                metadata={"label": "Workflow Label"}
            ),
        ),
        canvas_io_service=SimpleNamespace(
            resolve_node_meta_title=lambda node_data: node_data["_meta"]["title"],
            resolve_workflow_label=lambda metadata: metadata["label"],
        ),
        output_commit_handler=SimpleNamespace(
            commit_prepared_output_image=lambda _prepared: None,
            handle_output_image_preparation_failed=lambda _failure: None,
        ),
        output_canvas_projection_coordinator=ProjectionCoordinatorSpy(),
        canvas_host=SimpleNamespace(),
        generation_timing_lookup=timing_lookup,
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=CommitQueueSpy(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=project,
            active_workflow_id=lambda: "wf",
            output_canvas_visible=lambda: True,
        ),
    )
    payload = cast(
        dict[str, object],
        {"save": {"_meta": {"title": "SDXL/Text to Image.CubeOutput"}}},
    )

    pipeline.submit_output_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload=payload,
            file_path=Path("E:/out/001.png"),
            node_id="save",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf:save",
            source_label="Backend Save",
            list_index=0,
            artifact_width=1024,
            artifact_height=768,
        )
    )

    request = dispatcher.submitted[0]
    assert request.workflow_id == "wf"
    assert request.file_path == Path("E:/out/001.png")
    assert request.node_meta_title == "SDXL/Text to Image.CubeOutput"
    assert request.workflow_name == "Workflow Label"
    assert request.source_key == "wf:save"
    assert request.source_label == "Backend Save"
    assert request.generation_run_id == "run-1"
    assert request.prompt_id == "prompt-1"
    assert request.client_id == "client-1"
    assert request.position is not None
    assert request.position.list_index == 0
    assert request.position.batch_index == 0
    assert request.artifact_width == 1024
    assert request.artifact_height == 768
    assert request.live_event is not None
    assert request.cube_execution_duration_ms == 850.0
    assert timing_lookup.calls == [
        {
            "workflow_id": "wf",
            "source_key": "wf:save",
            "cube_alias": "Backend Save",
        }
    ]
    assert not hasattr(request, "workflow_payload")


def test_pipeline_preserves_backend_list_index_for_prepared_output_metadata() -> None:
    """Phase 0 - backend routing metadata survives into prepared Output metadata."""

    dispatcher = PreparationDispatcherSpy()

    def project(_workflow_id: str, _image_id: object = None) -> None:
        pass

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
        generation_timing_lookup=TimingLookupStub(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=CommitQueueSpy(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=project,
            active_workflow_id=lambda: "wf",
            output_canvas_visible=lambda: True,
        ),
    )

    pipeline.submit_output_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={
                "save": {"_meta": {"title": "Cube.Output"}},
            },
            file_path=Path("E:/out/004.png"),
            node_id="save",
            source_key="wf:save",
            source_label="Save",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            scene_run_id="scene-run",
            scene_key="scene-a",
            scene_title="Scene A",
            scene_order=2,
            scene_count=3,
            list_index=4,
            artifact_width=512,
            artifact_height=256,
        )
    )

    request = dispatcher.submitted[0]
    assert request.source_key == "wf:save"
    assert request.source_label == "Save"
    assert request.scene_run_id == "scene-run"
    assert request.scene_key == "scene-a"
    assert request.scene_title == "Scene A"
    assert request.scene_order == 2
    assert request.scene_count == 3
    assert request.position is not None
    assert request.position.list_index == 4
    assert request.position.batch_index == 0
    assert request.artifact_width == 512
    assert request.artifact_height == 256


def test_pipeline_rejects_live_update_missing_required_identity() -> None:
    """Live final updates should not build commit requests with fallback routing."""

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

    pipeline.submit_output_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={"save": {"_meta": {"title": "Cube.Output"}}},
            file_path=Path("E:/out/004.png"),
            node_id="save",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            list_index=4,
            artifact_width=512,
            artifact_height=256,
        )
    )

    assert dispatcher.submitted == []


@pytest.mark.parametrize(
    "field_updates",
    (
        {"workflow_id": ""},
        {"generation_run_id": None},
        {"prompt_id": None},
        {"client_id": None},
        {"source_key": ""},
        {"source_label": ""},
        {"node_id": ""},
        {"list_index": None},
        {"artifact_width": None},
        {"artifact_height": None},
    ),
)
def test_pipeline_rejects_live_update_with_any_missing_visual_identity(
    field_updates: dict[str, object],
) -> None:
    """Strict live request construction should fail closed for identity gaps."""

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
    base = OutputImageUpdate(
        workflow_id="wf",
        workflow_payload={"save": {"_meta": {"title": "Cube.Output"}}},
        file_path=Path("E:/out/004.png"),
        node_id="save",
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        source_key="wf:save",
        source_label="Cube",
        list_index=0,
        artifact_width=512,
        artifact_height=256,
    )

    pipeline.submit_output_update(replace(base, **cast(Any, field_updates)))

    assert dispatcher.submitted == []


def test_pipeline_rejects_live_update_with_negative_list_index() -> None:
    """Live final requests should reject unusable backend slot values."""

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

    pipeline.submit_output_update(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={"save": {"_meta": {"title": "Cube.Output"}}},
            file_path=Path("E:/out/004.png"),
            node_id="save",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf:save",
            source_label="Cube",
            list_index=-1,
            artifact_width=512,
            artifact_height=256,
        )
    )

    assert dispatcher.submitted == []
