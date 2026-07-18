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

"""Contract tests for final output image pipeline request construction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from substitute.application.ports import OutputImageUpdate
from substitute.application.workflows.output_canvas_state_service import (
    OutputProjectionSchedulingIntent,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
    ProjectionReason,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
)
from substitute.presentation.shell.output_image_pipeline import OutputImagePipeline


class _Signal:
    def __init__(self) -> None:
        self.callbacks: list[Callable[[str], None]] = []

    def connect(self, callback: Callable[[str], None]) -> None:
        self.callbacks.append(callback)


class _Dispatcher:
    def __init__(self) -> None:
        self.prepared = _Signal()
        self.failed = _Signal()
        self.submitted: list[OutputImageCommitRequest] = []

    def submit(self, request: OutputImageCommitRequest) -> None:
        self.submitted.append(request)


class _CommitQueue:
    def enqueue_prepared(self, output: object) -> None:
        _ = output

    def enqueue_failed(self, failure: object) -> None:
        _ = failure


class _Scheduler:
    """Capture projection scheduler requests without timers."""

    def __init__(self) -> None:
        """Initialize captured scheduler calls."""

        self.requests: list[tuple[str, object, object]] = []
        self.discarded: list[str] = []
        self.renamed: list[tuple[str, str]] = []

    def request_projection(
        self,
        workflow_id: str,
        *,
        reason: object,
        registered_image_id: object = None,
    ) -> None:
        """Capture one projection request."""

        self.requests.append((workflow_id, reason, registered_image_id))

    def flush_pending_for_workflow(self, _workflow_id: str) -> None:
        """Accept flush requests for protocol compatibility."""

    def discard_workflow(self, workflow_id: str) -> None:
        """Capture workflow cleanup requests."""

        self.discarded.append(workflow_id)

    def rename_workflow(self, old_workflow_id: str, new_workflow_id: str) -> None:
        """Capture workflow rename requests."""

        self.renamed.append((old_workflow_id, new_workflow_id))


class _ProjectionCoordinator:
    """Capture direct Output projection coordinator calls."""

    def __init__(self) -> None:
        """Initialize captured projection calls."""

        self.projected: list[tuple[object, str, object]] = []

    def project_workflow(
        self,
        workflows: object,
        active_workflow_id: str,
        *,
        registered_image_id: object = None,
    ) -> None:
        """Record one active Output projection request."""

        self.projected.append((workflows, active_workflow_id, registered_image_id))


class _TimingLookup:
    """Return deterministic cube timing for output pipeline tests."""

    def __init__(self) -> None:
        """Initialize lookup call capture."""

        self.calls: list[dict[str, str]] = []

    def cube_execution_duration_ms(
        self,
        *,
        workflow_id: str,
        source_key: str = "",
        cube_alias: str = "",
    ) -> float | None:
        """Record the lookup request and return a fixed duration."""

        self.calls.append(
            {
                "workflow_id": workflow_id,
                "source_key": source_key,
                "cube_alias": cube_alias,
            }
        )
        return 850.0


def _noop_project_workflow(
    _workflow_id: str,
    _registered_image_id: object = None,
) -> None:
    """Accept projection callbacks for tests that do not inspect projection."""


def _pipeline_shell_dependencies() -> dict[str, Any]:
    """Return shell collaborators irrelevant to route/visibility tests."""

    return {
        "workflow_session_service": SimpleNamespace(
            active_workflow_id="wf",
            workflows={"wf": object()},
            get_workflow=lambda _workflow_id: SimpleNamespace(metadata={}),
        ),
        "canvas_io_service": SimpleNamespace(
            resolve_node_meta_title=lambda _node_data: "Cube.Output",
            resolve_workflow_label=lambda _metadata: "Workflow",
        ),
        "output_commit_handler": SimpleNamespace(
            commit_prepared_output_image=lambda _prepared: None,
            handle_output_image_preparation_failed=lambda _failure: None,
        ),
        "output_canvas_projection_coordinator": _ProjectionCoordinator(),
        "preparation_dispatcher": _Dispatcher(),
        "commit_queue": _CommitQueue(),
    }


def test_pipeline_uses_host_activation_signal_for_output_projection() -> None:
    """Output projection should subscribe to host activation, not pivot internals."""

    scheduler = _Scheduler()
    signal = _Signal()
    canvas_tabs = SimpleNamespace(canvas_activated=signal)

    OutputImagePipeline(
        **_pipeline_shell_dependencies(),
        canvas_tabs=canvas_tabs,
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
        **_pipeline_shell_dependencies(),
        canvas_tabs=SimpleNamespace(
            is_canvas_visible=is_canvas_visible,
        ),
        projection_scheduler=_Scheduler(),  # type: ignore[arg-type]
    )

    assert pipeline._output_canvas_is_visible() is False
    assert calls == ["Output"]


def test_pipeline_projects_through_output_projection_coordinator() -> None:
    """Default projection scheduling should not use shell pass-through facades."""

    workflows = {"wf": object(), "inactive": object()}
    coordinator = _ProjectionCoordinator()
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
        canvas_tabs=SimpleNamespace(is_canvas_visible=lambda _label: True),
        preparation_dispatcher=_Dispatcher(),  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
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

    scheduler = _Scheduler()
    pipeline = OutputImagePipeline(
        **_pipeline_shell_dependencies(),
        canvas_tabs=SimpleNamespace(),
        projection_scheduler=scheduler,  # type: ignore[arg-type]
    )

    pipeline.remove_workflow("wf-closed")

    assert scheduler.discarded == ["wf-closed"]


def test_pipeline_rekeys_pending_projection_work_for_renamed_workflow() -> None:
    """Workflow rename should be delegated to the scheduler owner."""

    scheduler = _Scheduler()
    pipeline = OutputImagePipeline(
        **_pipeline_shell_dependencies(),
        canvas_tabs=SimpleNamespace(),
        projection_scheduler=scheduler,  # type: ignore[arg-type]
    )

    pipeline.rename_workflow("wf-old", "wf-new")

    assert scheduler.renamed == [("wf-old", "wf-new")]


def test_pipeline_builds_strict_live_request_without_retaining_payload() -> None:
    """Live request construction should capture strict backend metadata only."""

    dispatcher = _Dispatcher()

    def project(_workflow_id: str, _image_id: object = None) -> None:
        pass

    timing_lookup = _TimingLookup()
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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        generation_timing_lookup=timing_lookup,
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
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

    dispatcher = _Dispatcher()

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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        generation_timing_lookup=_TimingLookup(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
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

    dispatcher = _Dispatcher()

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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=_noop_project_workflow,
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

    dispatcher = _Dispatcher()
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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=_noop_project_workflow,
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

    dispatcher = _Dispatcher()

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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=_noop_project_workflow,
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


def test_pipeline_legacy_submit_preserves_explicit_fallback_metadata() -> None:
    """Explicit non-live submission should retain restore/import fallback behavior."""

    dispatcher = _Dispatcher()

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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        preparation_dispatcher=dispatcher,  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
        projection_scheduler=CanvasProjectionScheduler(
            project_workflow=_noop_project_workflow,
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
        output_canvas_projection_coordinator=_ProjectionCoordinator(),
        canvas_tabs=SimpleNamespace(),
        preparation_dispatcher=_Dispatcher(),  # type: ignore[arg-type]
        commit_queue=_CommitQueue(),  # type: ignore[arg-type]
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
