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

import ast
import uuid
from pathlib import Path

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_projection import (
    build_output_canvas_projection,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
    OutputVisualIdentity,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


def test_register_generated_output_preserves_backend_metadata_and_result_identity() -> (
    None
):
    """Live final registration should retain backend routing in registry metadata."""

    image_id = uuid.uuid4()
    registry = CanvasImageRegistry()
    service = OutputCanvasStateService(
        image_registry=registry,
        uuid_factory=lambda: image_id,
    )
    workflow = WorkflowState()
    image = object()
    event = _live_final_event()
    image_meta = _live_image_meta()

    result = service.register_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=event,
        image=image,
        image_meta=image_meta,
    )

    assert result.registered is True
    assert result.workflow_id == "wf"
    assert result.image_id == image_id
    assert result.focus_change.changed is True
    assert result.projection_intent.workflow_id == "wf"
    assert result.projection_intent.registered_image_id == image_id
    assert result.projection_intent.should_schedule is True
    assert result.preview_close_identity is not None
    assert result.preview_close_identity.node_id == "save-node"
    assert result.preview_close_identity.list_index == 2
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

    projection = build_output_canvas_projection(
        workflow,
        registry.metadata_for_ids(workflow.output_image_uuids),
    )
    assert projection.sources[0].images_by_set[3].image_id == image_id


def test_register_generated_output_rejects_node_mismatch() -> None:
    """Live final registration should fail closed when node identity drifts."""

    registry = CanvasImageRegistry()
    service = OutputCanvasStateService(image_registry=registry)
    workflow = WorkflowState()
    image_meta = _live_image_meta(node_id="other-node")

    result = service.register_generated_output(
        {"wf": workflow},
        active_workflow_id="wf",
        event=_live_final_event(),
        image=object(),
        image_meta=image_meta,
    )

    assert result.registered is False
    assert result.image_id is None
    assert workflow.output_image_uuids == []
    assert registry.metadata_mapping() == {}


def test_restore_output_image_writes_registry_without_membership_or_widgets() -> None:
    """Snapshot restore should only write the shared image registry."""

    registry = CanvasImageRegistry()
    service = OutputCanvasStateService(image_registry=registry)
    image_id = uuid.uuid4()
    image = object()
    image_meta = ImageMeta("wf", "Cube", 1, "", "E:/restored.png")

    result = service.restore_output_image(
        workflow_id="wf",
        image_id=image_id,
        image=image,
        image_meta=image_meta,
    )

    assert result.registered is True
    assert result.workflow_id == "wf"
    assert result.image_id == image_id
    assert result.projection_intent.workflow_id == "wf"
    assert result.projection_intent.should_schedule is False
    assert registry.payload_for(image_id) is image
    assert registry.metadata_for(image_id) == image_meta


def test_timing_focus_compare_and_pruning_are_owned_by_output_state_service() -> None:
    """The service should own durable Output timing, focus, compare, and pruning."""

    registry = CanvasImageRegistry()
    service = OutputCanvasStateService(image_registry=registry)
    workflow = WorkflowState()
    image_id = uuid.uuid4()
    workflow.output_image_uuids = [image_id]
    registry.store(
        image_id,
        payload=object(),
        metadata=ImageMeta(
            "wf",
            "Cube",
            1,
            "",
            "E:/out.png",
            source_key="wf:save",
            source_label="Save",
            scene_key="scene-a",
        ),
    )

    timing = service.apply_output_source_timing(
        {"wf": workflow},
        workflow_id="wf",
        active_workflow_id="wf",
        source_durations_ms={"wf:save": 55.0},
        cube_durations_ms={},
    )
    service.set_active_output_uuid(workflow, str(image_id))
    compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 1, "wf:save"),
    )
    service.set_output_compare_state(workflow, compare_state)

    assert timing.changed is True
    assert timing.projection_intent.should_schedule is True
    updated_meta = registry.metadata_for(image_id)
    assert updated_meta is not None
    assert updated_meta.cube_execution_duration_ms == 55.0
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert workflow.active_output_uuid == image_id
    assert workflow.active_output_source_key == "wf:save"
    assert workflow.active_output_set_index == 1
    assert workflow.active_output_scene_key == "scene-a"
    assert workflow.output_compare_state == compare_state

    prune = service.clear_output_for_workflow({"wf": workflow}, "wf")

    assert prune.removed_image_ids == (image_id,)
    assert workflow.output_image_uuids == []
    assert workflow.active_output_uuid is None
    assert workflow.output_focus_mode is OutputFocusMode.AUTOMATIC
    assert registry.metadata_for(image_id) is None


def test_output_canvas_state_service_has_no_widget_or_display_dependencies() -> None:
    """The Output state owner must stay pure application state."""

    module_path = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "application"
        / "workflows"
        / "output_canvas_state_service.py"
    )
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    forbidden_imports = {
        name
        for name in imported_modules
        if name.startswith(
            (
                "PySide6",
                "qfluentwidgets",
                "qpane",
                "substitute.presentation",
                "substitute.infrastructure.comfy",
            )
        )
    }
    forbidden_tokens = {
        token
        for token in (
            "QWidget",
            "QImage",
            "QPane",
            "canvas_tabs",
            "currentRouteKey",
            "setCurrentImageID",
            "addImage",
            "removeImageByID",
            "OutputCanvasView",
            "CanvasProjectionScheduler",
            "ProjectionReason",
            "websocket",
        )
        if token in source
    }

    assert forbidden_imports == set()
    assert forbidden_tokens == set()


def _live_final_event() -> LiveFinalOutputEvent:
    """Return one strict live final event for Output state tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            client_id="client-1",
            source_key="wf:save",
            source_label="Save",
            scene=OutputSceneIdentity(
                run_id="scene-run",
                key="scene-a",
                title="Scene A",
                order=1,
                count=3,
            ),
        ),
        node_id="save-node",
        workflow_payload={"save-node": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        list_index=2,
        artifact_width=640,
        artifact_height=480,
    )


def _live_image_meta(node_id: str = "save-node") -> ImageMeta:
    """Return metadata matching the strict live final event."""

    return ImageMeta(
        workflow_name="Workflow",
        cube_name="Save",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:save",
        source_label="Save",
        node_id=node_id,
        generation_run_id="run-1",
        prompt_id="prompt-1",
        client_id="client-1",
        scene_run_id="scene-run",
        scene_key="scene-a",
        scene_title="Scene A",
        scene_order=1,
        scene_count=3,
        width=640,
        height=480,
        list_index=2,
        cube_execution_duration_ms=123.0,
    )
