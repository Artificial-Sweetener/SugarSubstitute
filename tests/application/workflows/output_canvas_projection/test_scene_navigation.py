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

"""Verify Output projection navigation across scene scopes."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import OutputFocusMode, WorkflowState


from tests.application.workflows.output_canvas_projection.support import build_meta


def test_projection_automatic_multi_scene_same_source_stays_on_scene_overview() -> None:
    """Automatic scene runs should not promote cross-scene source groups to grids."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.active_output_uuid = ids[-1]
    workflow.active_output_source_key = "wf:text"
    metadata = {
        ids[0]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.scene_count == 2
    assert projection.active_scene_overview is True
    assert projection.active_scene_key == "cafe"
    assert projection.active_set_index == 1
    assert projection.active_uuid is None


def test_projection_automatic_stays_all_with_multiple_populated_scenes() -> None:
    """Keep Automatic on scene overview while later scene batches arrive."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(8)]
    workflow.output_image_uuids = ids[:7]
    metadata = {
        image_id: build_meta(
            "Text to Image" if item_index % 2 == 0 else "Diffusion Upscale",
            source_key="wf:text" if item_index % 2 == 0 else "wf:upscale",
            scene_key=f"scene-{item_index // 2 + 1}",
            scene_title=f"Scene {item_index // 2 + 1}",
            scene_order=item_index // 2,
            scene_count=3,
            list_index=0,
            batch_index=0,
            generation_run_id=f"run-{item_index // 2 + 1}",
            output_session_id="session-1",
        )
        for item_index, image_id in enumerate(ids[:6])
    }
    metadata[ids[6]] = build_meta(
        "Text to Image",
        source_key="wf:text",
        scene_key="scene-1",
        scene_title="Scene 1",
        scene_order=0,
        scene_count=3,
        list_index=0,
        batch_index=0,
        generation_run_id="run-4",
        output_session_id="session-1",
    )

    text_projection = build_output_canvas_projection(workflow, metadata)

    assert text_projection.active_scene_key == "scene-1"
    assert text_projection.active_scene_overview is True
    assert text_projection.active_source_key is None
    assert text_projection.active_set_index == 1
    assert text_projection.active_uuid is None

    workflow.output_image_uuids.append(ids[7])
    metadata[ids[7]] = build_meta(
        "Diffusion Upscale",
        source_key="wf:upscale",
        scene_key="scene-1",
        scene_title="Scene 1",
        scene_order=0,
        scene_count=3,
        list_index=0,
        batch_index=0,
        generation_run_id="run-4",
        output_session_id="session-1",
    )

    upscale_projection = build_output_canvas_projection(workflow, metadata)

    assert upscale_projection.active_scene_key == "scene-1"
    assert upscale_projection.active_scene_overview is True
    assert upscale_projection.active_source_key is None
    assert upscale_projection.active_set_index == 1
    assert upscale_projection.active_uuid is None


def test_projection_manual_scene_overview_stays_on_scene_overview() -> None:
    """Manual All selection should remain active across later scene outputs."""

    workflow = WorkflowState()
    ids = [uuid4(), uuid4()]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_overview = True
    workflow.active_output_scene_key = "portrait"
    workflow.active_output_uuid = None
    workflow.active_output_source_key = None
    workflow.active_output_set_index = 1
    metadata = {
        ids[0]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.active_scene_overview is True
    assert projection.active_scene_key == "portrait"
    assert projection.active_source_key is None
    assert projection.active_set_index == 1
    assert projection.active_uuid is None


def test_projection_manual_concrete_scene_scopes_focus_to_scene_sources() -> None:
    """Manual scene grid focus should resolve inside the selected scene only."""

    workflow = WorkflowState()
    ids = [uuid4() for _ in range(4)]
    workflow.output_image_uuids = ids
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_key = "portrait"
    workflow.active_output_scene_overview = False
    workflow.active_output_uuid = None
    workflow.active_output_source_key = "wf:text"
    workflow.active_output_set_index = 0
    metadata = {
        ids[0]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[1]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="portrait",
            scene_title="Portrait",
            scene_order=0,
            scene_count=2,
        ),
        ids[2]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=1,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
        ids[3]: build_meta(
            "Text",
            source_key="wf:text",
            image_number=2,
            scene_key="cafe",
            scene_title="Cafe",
            scene_order=1,
            scene_count=2,
        ),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert projection.active_scene_overview is False
    assert projection.active_scene_key == "portrait"
    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 0
    assert projection.active_uuid is None


def test_projection_waits_for_multiple_populated_scenes_before_overview() -> None:
    """Scene overview should remain unavailable until two scenes have output."""

    workflow = WorkflowState()
    image_id = uuid4()
    workflow.output_image_uuids = [image_id]
    workflow.active_output_uuid = image_id

    projection = build_output_canvas_projection(
        workflow,
        {
            image_id: build_meta(
                "Text",
                source_key="wf:text",
                scene_key="portrait",
                scene_title="Portrait",
                scene_order=0,
                scene_count=3,
            )
        },
    )

    assert projection.scene_count == 1
    assert projection.active_scene_overview is False
    assert projection.active_scene_key == "portrait"
    assert projection.active_source_key == "wf:text"
    assert projection.active_set_index == 1
    assert projection.active_uuid == image_id
