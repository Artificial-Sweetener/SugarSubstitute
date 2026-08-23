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

"""Verify final-output commands consume pending preview retirement."""

from __future__ import annotations

from uuid import uuid4

from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
    consume_final_output_preview_retirement,
    final_output_preview_retirement,
)
from substitute.domain.workflow import (
    ImageMeta,
)


def test_final_output_preview_retirement_returns_completed_slot_command() -> None:
    """Final-output selection should expose the preview slot it supersedes."""

    final_id = uuid4()
    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    retirement = final_output_preview_retirement(
        image_id=final_id,
        pending_final_preview_retire_ids={final_id},
        source_key="wf:upscale",
        image_meta=metadata,
        set_index=2,
    )

    assert retirement is not None
    assert retirement.slot_key == PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )
    assert retirement.source_label == "Upscale"


def test_consume_final_output_preview_retirement_removes_pending_id() -> None:
    """Pending final-output retirements should be consumed with their command."""

    final_id = uuid4()
    other_id = uuid4()
    pending_ids = {final_id, other_id}
    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    retirement = consume_final_output_preview_retirement(
        image_id=final_id,
        pending_final_preview_retire_ids=pending_ids,
        source_key="wf:upscale",
        image_meta=metadata,
        set_index=2,
    )

    assert retirement is not None
    assert retirement.slot_key == PreviewSlotKey(
        scene_run_id="scene-run",
        generation_run_id="generation-run",
        scene_key="portrait",
        source_key="wf:upscale",
        set_index=2,
    )
    assert pending_ids == {other_id}


def test_final_output_preview_retirement_ignores_non_pending_output() -> None:
    """Final-output selection should not retire previews unless the final is pending."""

    metadata = ImageMeta(
        workflow_name="Workflow",
        cube_name="Upscale",
        image_number=1,
        suffix="",
        path="E:/out.png",
        source_key="wf:upscale",
        source_label="Upscale",
        generation_run_id="generation-run",
        scene_run_id="scene-run",
        scene_key="portrait",
    )

    assert (
        final_output_preview_retirement(
            image_id=uuid4(),
            pending_final_preview_retire_ids={uuid4()},
            source_key="wf:upscale",
            image_meta=metadata,
            set_index=2,
        )
        is None
    )
