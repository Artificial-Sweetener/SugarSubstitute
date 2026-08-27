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

"""Contract tests for prompt-scene output run state tracking."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows import OutputSceneRunService


def test_scene_run_service_tracks_manifest_and_visual_attachments() -> None:
    """Scene runs should preserve authority order and attach preview/final images."""

    service = OutputSceneRunService()
    preview_id = uuid4()
    output_id = uuid4()

    service.start_scene_run(
        scene_run_id="run-1",
        workflow_id="wf-1",
        workflow_name="Recipe",
        scenes=(("portrait", "Portrait", 0), ("cafe", "Cafe", 1)),
    )
    service.mark_scene_running(
        scene_run_id="run-1",
        scene_key="portrait",
        job_id="job-1",
    )
    service.attach_preview(
        scene_run_id="run-1",
        scene_key="portrait",
        preview_id=preview_id,
    )
    state = service.attach_output(
        scene_run_id="run-1",
        scene_key="portrait",
        output_id=output_id,
    )

    assert state is not None
    portrait = state.scene_for_key("portrait")
    assert portrait is not None
    assert portrait.status == "running"
    assert portrait.job_id == "job-1"
    assert portrait.preview_id is None
    assert portrait.final_output_ids == (output_id,)
    assert portrait.has_visual_content is True
    assert [scene.scene_key for scene in state.scenes] == ["portrait", "cafe"]


def test_scene_run_service_discards_preview_only_cancelled_scene() -> None:
    """Cancelled preview-only scenes should remain known but not inspectable."""

    service = OutputSceneRunService()
    preview_id = uuid4()

    service.start_scene_run(
        scene_run_id="run-1",
        workflow_id="wf-1",
        workflow_name="Recipe",
        scenes=(("portrait", "Portrait", 0),),
    )
    service.attach_preview(
        scene_run_id="run-1",
        scene_key="portrait",
        preview_id=preview_id,
    )
    state = service.mark_scene_cancelled(
        scene_run_id="run-1",
        scene_key="portrait",
    )

    assert state is not None
    portrait = state.scene_for_key("portrait")
    assert portrait is not None
    assert portrait.status == "cancelled"
    assert portrait.preview_id is None
    assert portrait.final_output_ids == ()
    assert portrait.has_visual_content is False


def test_scene_run_service_preserves_final_output_for_skipped_scene() -> None:
    """Skipped scenes should remain inspectable when they already have final output."""

    service = OutputSceneRunService()
    output_id = uuid4()

    service.start_scene_run(
        scene_run_id="run-1",
        workflow_id="wf-1",
        workflow_name="Recipe",
        scenes=(("portrait", "Portrait", 0),),
    )
    service.attach_output(
        scene_run_id="run-1",
        scene_key="portrait",
        output_id=output_id,
    )
    state = service.mark_scene_skipped(
        scene_run_id="run-1",
        scene_key="portrait",
    )

    assert state is not None
    portrait = state.scene_for_key("portrait")
    assert portrait is not None
    assert portrait.status == "skipped"
    assert portrait.final_output_ids == (output_id,)
    assert portrait.has_visual_content is True
