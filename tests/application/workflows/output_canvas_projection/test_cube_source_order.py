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

"""Ensure Output source tabs follow authored Cube order after restoration."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import build_output_canvas_projection
from substitute.domain.workflow import OutputFocusMode
from tests.application.workflows.output_canvas_projection.support import build_meta
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


def test_cube_tabs_follow_authored_stack_when_video_was_registered_first() -> None:
    """Stored arrival order must not reorder Cube tabs or change manual focus."""

    workflow = graph_backed_cube_workflow("z-image", "a-video")
    image_id = uuid4()
    video_id = uuid4()
    workflow.output_image_uuids = [video_id, image_id]
    workflow.active_output_uuid = video_id
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    metadata = {
        video_id: build_meta("Video", source_key="cube:a-video"),
        image_id: build_meta("Image", source_key="cube:z-image"),
    }

    projection = build_output_canvas_projection(workflow, metadata)

    assert [source.source_key for source in projection.sources] == [
        "cube:z-image",
        "cube:a-video",
    ]
    assert [source.source_key for source in projection.scene_groups[0].sources] == [
        "cube:z-image",
        "cube:a-video",
    ]
    assert projection.active_uuid == video_id
