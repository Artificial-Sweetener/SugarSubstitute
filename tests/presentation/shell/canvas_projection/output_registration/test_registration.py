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

"""Characterize canvas projection output registration contracts."""

from __future__ import annotations

import uuid
from pathlib import Path

from _pytest.logging import LogCaptureFixture
from PySide6.QtGui import QImage

from substitute.application.workflows.output_canvas_state_service import (
    OutputImageRegistrationResult,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.domain.generation import OutputResultPosition
from substitute.domain.workflow import (
    ImageMeta,
    WorkflowState,
)
from substitute.presentation.shell.canvas_projection_scheduler import (
    CanvasProjectionScheduler,
)
from substitute.presentation.shell.output_image_commit_pipeline import (
    OutputImageCommitRequest,
    PreparedOutputImage,
)
from substitute.presentation.shell.output_image_commit_queue import (
    PreparedOutputCommitQueue,
)


from ..support.harness import (
    _add_output_image,
    _app,
    _build_service,
)
from ..support.output_events import _live_final_event


def test_register_output_image_does_not_touch_pane_or_projection() -> None:
    """Output registration should update state without mutating visible widgets."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
    )

    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    assert result.image_id in workflow.output_image_uuids
    assert service.image_registry.payload_for(result.image_id) is image
    assert service.image_registry.metadata_for(result.image_id) == image_meta
    assert output_pane.images == {}
    assert output_canvas.register_calls == []
    assert output_canvas.sync_calls == []


def test_inactive_output_registration_updates_only_target_workflow_state() -> None:
    """Inactive final output arrival should not mutate the visible workflow or pane."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "Inactive",
        "Cube",
        1,
        "",
        "E:/inactive.png",
        source_key="wf-b:node",
    )

    result = service.output_canvas_state_service.register_output_image(
        {"wf-a": active_workflow, "wf-b": inactive_workflow},
        origin_workflow_id="wf-b",
        active_workflow_id="wf-a",
        image=image,
        image_meta=image_meta,
    )

    assert result.projection_intent.should_schedule is False
    assert result.image_id in inactive_workflow.output_image_uuids
    assert active_workflow.output_image_uuids == []
    assert active_workflow.active_output_uuid is None
    assert service.image_registry.payload_for(result.image_id) is image
    assert service.image_registry.metadata_for(result.image_id) == image_meta
    assert output_pane.images == {}
    assert output_canvas.sync_calls == []


def test_inactive_prepared_output_commit_preserves_visible_qpane_route() -> None:
    """Inactive final output commits should not schedule or apply visible routes."""

    _app()
    service, _input_pane, output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    workflows = {"wf-a": active_workflow, "wf-b": inactive_workflow}
    active_image = object()
    inactive_image = object()
    active_meta = ImageMeta(
        "Active",
        "Active Cube",
        1,
        "",
        "E:/active.png",
        source_key="wf-a:node",
    )
    inactive_meta = ImageMeta(
        "Inactive",
        "Inactive Cube",
        1,
        "",
        "E:/inactive.png",
        source_key="wf-b:node",
    )
    active_result = service.output_canvas_state_service.register_output_image(
        workflows,
        origin_workflow_id="wf-a",
        active_workflow_id="wf-a",
        image=active_image,
        image_meta=active_meta,
    )
    service.project_output(
        workflows,
        "wf-a",
        registered_image_id=active_result.image_id,
    )
    visible_image_id = output_pane.current_id
    output_canvas.sync_calls.clear()
    output_pane.selection_calls.clear()
    scheduled_projection_calls: list[tuple[str, uuid.UUID | None]] = []

    def project_workflow(
        workflow_id: str,
        registered_image_id: uuid.UUID | None = None,
    ) -> None:
        scheduled_projection_calls.append((workflow_id, registered_image_id))
        service.project_output(
            workflows,
            workflow_id,
            registered_image_id=registered_image_id,
        )

    scheduler = CanvasProjectionScheduler(
        project_workflow=project_workflow,
        active_workflow_id=lambda: "wf-a",
        output_canvas_visible=lambda: True,
    )

    def commit_prepared(
        _prepared: PreparedOutputImage,
    ) -> OutputImageRegistrationResult:
        return service.output_canvas_state_service.register_output_image(
            workflows,
            origin_workflow_id="wf-b",
            active_workflow_id="wf-a",
            image=inactive_image,
            image_meta=inactive_meta,
        )

    queue = PreparedOutputCommitQueue(
        commit_prepared=commit_prepared,
        handle_failure=lambda _failure: None,
        projection_scheduler=scheduler,
        output_activity_marker=lambda _reason: None,
    )
    queue.enqueue_prepared(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-b",
                file_path=Path("E:/inactive.png"),
                node_id="node",
                node_meta_title="Inactive.Output",
                workflow_name="Inactive",
                source_key="wf-b:node",
                source_label="Inactive Cube",
            ),
            image=QImage(8, 8, QImage.Format.Format_ARGB32),
        )
    )

    queue.drain_once()

    assert inactive_workflow.output_image_uuids
    assert active_workflow.output_image_uuids == [visible_image_id]
    assert output_pane.current_id == visible_image_id
    assert output_pane.selection_calls == []
    assert output_canvas.sync_calls == []
    assert scheduled_projection_calls == []
    assert output_pane.images == {
        visible_image_id: (active_image, Path("E:/active.png"))
    }


def test_register_output_image_does_not_warm_visible_pane() -> None:
    """Final output registration should leave visible QPane routes untouched."""

    service, _input_pane, output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/out.png")
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    assert result.image_id is not None
    assert output_pane.add_calls == []
    assert output_pane.current_id is None


def test_project_output_warms_output_catalog_and_syncs() -> None:
    """Scheduled projection should cache projected images before route application."""

    service, _input_pane, output_pane, output_canvas = _build_service()
    workflow = WorkflowState()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
    )
    result = service.output_canvas_state_service.register_output_image(
        {"wf": workflow},
        origin_workflow_id="wf",
        active_workflow_id="wf",
        image=image,
        image_meta=image_meta,
    )

    service.project_output(
        {"wf": workflow},
        "wf",
        registered_image_id=result.image_id,
    )

    assert output_canvas.register_calls == []
    assert output_canvas.sync_calls
    assert output_pane.add_calls == [(result.image_id, image, Path("E:/out.png"))]
    assert output_pane.current_id == result.image_id


def test_inactive_scene_output_updates_origin_without_projecting_active_canvas() -> (
    None
):
    """Inactive workflow scene outputs should not overwrite active canvas projection."""

    service, _input_pane, _output_pane, output_canvas = _build_service()
    active_workflow = WorkflowState()
    inactive_workflow = WorkflowState()
    workflows = {"active": active_workflow, "inactive": inactive_workflow}

    _add_output_image(
        service,
        workflows,
        origin_workflow_id="inactive",
        active_workflow_id="active",
        image=object(),
        image_meta=ImageMeta(
            "inactive",
            "Text",
            1,
            "",
            "E:/inactive.png",
            source_key="inactive:text",
            source_label="Inactive Text",
            scene_run_id="run-inactive",
            scene_key="scene2",
            scene_title="Inactive Two",
            scene_order=1,
            scene_count=2,
        ),
    )

    assert output_canvas.sync_calls == []
    assert inactive_workflow.output_image_uuids
    assert inactive_workflow.active_output_source_key is None
    assert inactive_workflow.active_output_scene_key is None
    assert inactive_workflow.active_output_scene_overview is False
    assert active_workflow.active_output_source_key is None
    assert active_workflow.active_output_scene_key is None


def test_register_generated_output_rejects_missing_workflow(
    caplog: LogCaptureFixture,
) -> None:
    """Strict live registration should reject missing workflow identity."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    image = object()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=0,
        batch_index=0,
        width=640,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_generated_result_service.commit_generated_output(
        {},
        active_workflow_id="wf",
        event=_live_final_event(),
        image=image,
        image_meta=image_meta,
    )

    assert result.workflow_id == "wf"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert result.image_id is None
    assert "missing_workflow" in caplog.text
    assert "source_key=wf:node" in caplog.text


def test_register_generated_output_rejects_metadata_identity_mismatch(
    caplog: LogCaptureFixture,
) -> None:
    """Strict live registration should fail closed on metadata identity drift."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=2,
        width=640,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_generated_result_service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=_live_final_event(),
        image=object(),
        image_meta=image_meta,
    )

    assert result.workflow_id == "wf"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert workflow.output_image_uuids == []
    assert "list_index_mismatch" in caplog.text


def test_register_generated_output_rejects_dimension_or_scene_drift(
    caplog: LogCaptureFixture,
) -> None:
    """Strict live registration should verify dimensions and scene identity."""

    service, _input_pane, _output_pane, _output_canvas = _build_service()
    workflow = WorkflowState()
    event = LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:node",
            source_label="Cube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="node",
        workflow_payload={"node": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        position=OutputResultPosition(list_index=0, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )
    image_meta = ImageMeta(
        "wf",
        "Cube",
        1,
        "",
        "E:/out.png",
        source_key="wf:node",
        source_label="Cube",
        node_id="node",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        list_index=0,
        width=639,
        height=480,
    )
    caplog.set_level(
        "WARNING",
        logger="sugarsubstitute.application.workflows.output_canvas_state_service",
    )

    result = service.output_generated_result_service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=event,
        image=object(),
        image_meta=image_meta,
    )

    assert result.registered is False
    assert workflow.output_image_uuids == []
    assert result.image_id is None
    assert "artifact_width_mismatch" in caplog.text
