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

"""Contract tests for durable Output canvas state ownership."""

from __future__ import annotations

import uuid
from dataclasses import replace

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_projection import (
    build_output_canvas_projection,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_generated_result_service import (
    OutputGeneratedResultService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.domain.workflow import (
    OutputFocusMode,
    WorkflowState,
)


from tests.application.workflows.output_canvas_state.support import (
    build_live_final_event,
    build_live_image_meta,
)


def test_register_generated_output_preserves_backend_metadata_and_result_identity() -> (
    None
):
    """Live final registration should retain backend routing in registry metadata."""

    image_id = uuid.uuid4()
    registry = CanvasImageRegistry()
    state_service = OutputCanvasStateService(
        image_registry=registry,
        uuid_factory=lambda: image_id,
    )
    service = OutputGeneratedResultService(
        image_registry=registry,
        output_state_service=state_service,
        navigation_session_service=OutputNavigationSessionService(),
    )
    workflow = WorkflowState()
    image = object()
    event = build_live_final_event()
    image_meta = build_live_image_meta()

    result = service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=event,
        image=image,
        image_meta=image_meta,
    )

    assert result.registered is True
    assert result.workflow_id == "wf"
    assert result.image_id == image_id
    assert result.focus_change.changed is False
    assert result.projection_intent.workflow_id == "wf"
    assert result.projection_intent.registered_image_id == image_id
    assert result.projection_intent.should_schedule is True
    assert result.preview_close_identity is not None
    assert result.preview_close_identity.node_id == "save-node"
    assert result.preview_close_identity.list_index == 2
    assert result.preview_close_identity.batch_index == 0
    assert workflow.output_image_uuids == [image_id]
    assert registry.payload_for(image_id) is image

    stored_meta = registry.metadata_for(image_id)
    assert stored_meta is image_meta
    assert stored_meta is not None
    assert stored_meta.node_id == "save-node"
    assert stored_meta.source_key == "wf:save"
    assert stored_meta.source_label == "Save"
    assert stored_meta.generation_run_id == "run-1"
    assert stored_meta.prompt_id == "prompt-1"
    assert stored_meta.client_id == "client-1"
    assert stored_meta.scene_run_id == "scene-run"
    assert stored_meta.scene_key == "scene-a"
    assert stored_meta.scene_title == "Scene A"
    assert stored_meta.scene_order == 1
    assert stored_meta.scene_count == 3
    assert stored_meta.width == 640
    assert stored_meta.height == 480
    assert stored_meta.path == "E:/out.png"
    assert stored_meta.cube_execution_duration_ms == 123.0
    assert stored_meta.list_index == 2
    assert stored_meta.batch_index == 0

    projection = build_output_canvas_projection(
        workflow,
        registry.metadata_for_ids(workflow.output_image_uuids),
    )
    assert projection.sources[0].images_by_set[1].image_id == image_id


def test_first_final_replaces_the_previous_run_when_previews_are_disabled() -> None:
    """Hand the canvas to a new run when its first presentable result is final."""

    previous_id = uuid.uuid4()
    generated_id = uuid.uuid4()
    registry = CanvasImageRegistry()
    registry.store(
        previous_id,
        payload=object(),
        metadata=replace(build_live_image_meta(), output_session_id="old-run"),
    )
    state_service = OutputCanvasStateService(
        image_registry=registry,
        uuid_factory=lambda: generated_id,
    )
    service = OutputGeneratedResultService(
        image_registry=registry,
        output_state_service=state_service,
        navigation_session_service=OutputNavigationSessionService(),
    )
    workflow = WorkflowState(output_image_uuids=[previous_id])
    event = build_live_final_event()
    event = replace(
        event,
        identity=replace(event.identity, output_session_id="new-run"),
    )
    image_meta = replace(build_live_image_meta(), output_session_id="new-run")

    result = service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=event,
        image=object(),
        image_meta=image_meta,
    )

    assert result.registered is True
    assert result.retired_image_ids == (previous_id,)
    assert workflow.output_image_uuids == [generated_id]
    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC


def test_register_generated_output_preserves_manual_focus() -> None:
    """A final arriving after user navigation must not replace manual focus."""

    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    registry = CanvasImageRegistry()
    registry.store(first_id, payload=object(), metadata=build_live_image_meta())
    state_service = OutputCanvasStateService(
        image_registry=registry,
        uuid_factory=lambda: second_id,
    )
    focus_service = OutputCanvasFocusService(image_registry=registry)
    navigation_session_service = OutputNavigationSessionService()
    service = OutputGeneratedResultService(
        image_registry=registry,
        output_state_service=state_service,
        navigation_session_service=navigation_session_service,
    )
    workflow = WorkflowState()
    workflow.output_image_uuids = [first_id]
    output_session_id = build_live_image_meta().scene_run_id
    assert output_session_id is not None
    navigation_session_service.begin_session(
        {"wf": workflow},
        "wf",
        output_session_id,
    )
    navigation_session_service.present_session_content(
        {"wf": workflow},
        "wf",
        output_session_id,
    )
    navigation_session_service.mark_user_navigation("wf", workflow)
    focus_service.set_active_output_uuid(workflow, str(first_id))

    result = service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=build_live_final_event(),
        image=object(),
        image_meta=build_live_image_meta(),
    )

    assert result.registered is True
    assert workflow.output_image_uuids == [first_id, second_id]
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == first_id


def test_register_generated_output_rejects_node_mismatch() -> None:
    """Live final registration should fail closed when node identity drifts."""

    registry = CanvasImageRegistry()
    state_service = OutputCanvasStateService(image_registry=registry)
    service = OutputGeneratedResultService(
        image_registry=registry,
        output_state_service=state_service,
        navigation_session_service=OutputNavigationSessionService(),
    )
    workflow = WorkflowState()
    image_meta = build_live_image_meta(node_id="other-node")

    result = service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=build_live_final_event(),
        image=object(),
        image_meta=image_meta,
    )

    assert result.registered is False
    assert result.image_id is None
    assert workflow.output_image_uuids == []
    assert registry.metadata_mapping() == {}


def test_generated_result_replaces_prior_group_only_during_successful_commit() -> None:
    """A validated presentable final should atomically replace the prior result group."""

    old_id = uuid.uuid4()
    new_id = uuid.uuid4()
    registry = CanvasImageRegistry()
    old_meta = replace(
        build_live_image_meta(),
        generation_run_id="old-run",
        scene_run_id="old-scene-run",
    )
    registry.store(old_id, payload=object(), metadata=old_meta)
    workflow = WorkflowState(output_image_uuids=[old_id])
    state_service = OutputCanvasStateService(
        image_registry=registry,
        uuid_factory=lambda: new_id,
    )
    service = OutputGeneratedResultService(
        image_registry=registry,
        output_state_service=state_service,
        navigation_session_service=OutputNavigationSessionService(),
    )

    result = service.commit_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=build_live_final_event(),
        image=object(),
        image_meta=build_live_image_meta(),
    )

    assert result.registered is True
    assert result.image_id == new_id
    assert result.retired_image_ids == (old_id,)
    assert workflow.output_image_uuids == [new_id]
    assert registry.metadata_for(old_id) is None
    assert registry.metadata_for(new_id) is not None
