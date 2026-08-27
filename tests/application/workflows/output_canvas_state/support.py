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

"""Build representative Output canvas state contracts for tests."""

from pathlib import Path

from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputSceneIdentity,
    OutputVisualIdentity,
)
from substitute.domain.generation import OutputResultPosition
from substitute.domain.workflow import ImageMeta


def build_live_final_event() -> LiveFinalOutputEvent:
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
        position=OutputResultPosition(list_index=2, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )


def build_live_image_meta(node_id: str = "save-node") -> ImageMeta:
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
        batch_index=0,
        cube_execution_duration_ms=123.0,
    )
