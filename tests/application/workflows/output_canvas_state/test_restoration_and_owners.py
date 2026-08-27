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

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_canvas_timing_service import (
    OutputCanvasTimingService,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.domain.workflow import (
    ImageMeta,
    OutputCompareSelection,
    OutputCompareState,
    OutputFocusMode,
    WorkflowState,
)


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


def test_timing_focus_compare_and_pruning_use_their_authoritative_owners() -> None:
    """Durable Output metadata and focus should use separate cohesive owners."""

    registry = CanvasImageRegistry()
    service = OutputCanvasStateService(image_registry=registry)
    focus_service = OutputCanvasFocusService(image_registry=registry)
    navigation_session_service = OutputNavigationSessionService()
    timing_service = OutputCanvasTimingService(image_registry=registry)
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

    timing = timing_service.apply_output_source_timing(
        {"wf": workflow},
        workflow_id="wf",
        active_workflow_id="wf",
        source_durations_ms={"wf:save": 55.0},
        cube_durations_ms={},
    )
    navigation_session_service.mark_user_navigation("wf", workflow)
    focus_service.set_active_output_uuid(workflow, str(image_id))
    compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene-a", 1, "wf:save"),
    )
    focus_service.set_output_compare_state(workflow, compare_state)

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
    assert workflow.output_focus_mode is OutputFocusMode.MANUAL
    assert registry.metadata_for(image_id) is None
