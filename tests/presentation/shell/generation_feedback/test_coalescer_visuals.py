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

"""Test preview and final-output coalescing policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitute.application.generation import GenerationRunStarted
from substitute.application.ports import (
    OutputImageUpdate,
    PreviewImageUpdate,
)
from substitute.presentation.shell.generation_feedback_coalescer import (
    GenerationFeedbackCoalescer,
)


from tests.presentation.shell.generation_feedback.coalescer_support import (
    _live_output,
    _live_preview,
    _output_update,
    _preview_update,
    _run_started,
)


def test_preview_latest_frame_wins_per_source() -> None:
    """Preview coalescing should keep only the newest frame per source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = _preview_update(image="first")
    second = _preview_update(image="second")

    coalescer.submit_preview(first)
    coalescer.submit_preview(second)

    assert coalescer.drain_due().preview_updates == (_live_preview(second),)


def test_preview_keeps_separate_scene_slots() -> None:
    """Scene preview slots should not overwrite unrelated scene previews."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = PreviewImageUpdate(
        workflow_id="wf",
        image="first",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
        scene_run_id="run",
        scene_key="scene-a",
        scene_title="Scene A",
        scene_order=0,
        scene_count=2,
    )
    second = PreviewImageUpdate(
        workflow_id="wf",
        image="second",
        generation_run_id="run-1",
        prompt_id="pid-1",
        client_id="client-1",
        node_id="N1",
        source_key="wf:N1",
        source_label="Cube",
        scene_run_id="run",
        scene_key="scene-b",
        scene_title="Scene B",
        scene_order=1,
        scene_count=2,
    )

    coalescer.submit_preview(first)
    coalescer.submit_preview(second)

    assert coalescer.drain_due().preview_updates == (
        _live_preview(first),
        _live_preview(second),
    )


def test_output_images_are_not_coalesced(tmp_path: Path) -> None:
    """Final output image updates should remain lossless."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    first = _output_update(tmp_path / "first.png")
    second = _output_update(tmp_path / "second.png")

    coalescer.submit_output_image(first)
    coalescer.submit_output_image(second)

    assert coalescer.drain_all().output_image_updates == (
        _live_output(first),
        _live_output(second),
    )


def test_final_output_without_list_index_is_dropped(tmp_path: Path) -> None:
    """Live final output updates must carry backend list index identity."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_output_image(
        _output_update(tmp_path / "missing-index.png", list_index=None)
    )

    assert coalescer.drain_all().output_image_updates == ()


def test_rejected_live_visual_logging_includes_node_and_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Rejected visual updates should log useful prompt-safe routing context."""

    coalescer = GenerationFeedbackCoalescer()
    caplog.set_level(
        "DEBUG",
        logger="sugarsubstitute.presentation.shell.generation_feedback_coalescer",
    )

    coalescer.submit_output_image(
        OutputImageUpdate(
            workflow_id="wf",
            workflow_payload={"N1": {"class_type": "SaveImage"}},
            file_path=Path("missing.png"),
            node_id="N1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:N1",
            source_label="Cube",
            list_index=None,
            artifact_width=640,
            artifact_height=480,
        )
    )

    assert "client_id=client-1" in caplog.text
    assert "node_id=N1" in caplog.text
    assert "reason=missing_output_identity" in caplog.text


def test_preview_without_run_identity_is_dropped() -> None:
    """Preview events must not render until they can prove run ownership."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_preview(
        PreviewImageUpdate(workflow_id="wf", image="old", source_key="wf:N1")
    )

    assert coalescer.drain_due().preview_updates == ()


def test_requeue_stale_preview_is_dropped() -> None:
    """A new active run should make late previews from the previous prompt inert."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    coalescer.submit_run_started(
        GenerationRunStarted(
            workflow_id="wf",
            generation_run_id="run-2",
            output_session_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    coalescer.submit_preview(_preview_update(image="stale"))
    coalescer.submit_preview(
        _preview_update(
            image="current",
            generation_run_id="run-2",
            prompt_id="pid-2",
            client_id="client-2",
        )
    )

    current_preview = _preview_update(
        image="current",
        generation_run_id="run-2",
        prompt_id="pid-2",
        client_id="client-2",
    )
    assert coalescer.drain_due().preview_updates == (_live_preview(current_preview),)


def test_final_output_closes_late_preview_lane(tmp_path: Path) -> None:
    """A final image should remove pending previews and reject later matching ones."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    preview = _preview_update(image="preview")
    output = _output_update(tmp_path / "final.png")

    coalescer.submit_preview(preview)
    coalescer.submit_output_image(output)
    coalescer.submit_preview(_preview_update(image="late"))

    batch = coalescer.drain_all()

    assert batch.preview_updates == ()
    assert batch.output_image_updates == (_live_output(output),)


def test_final_output_does_not_close_other_cube_preview(tmp_path: Path) -> None:
    """Final lifecycle closure must be scoped to one output source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    cube_two = _preview_update(image="cube-2", source_key="wf:N2")

    coalescer.submit_output_image(_output_update(tmp_path / "cube-1.png"))
    coalescer.submit_preview(cube_two)

    assert coalescer.drain_all().preview_updates == (_live_preview(cube_two),)


def test_final_output_does_not_close_other_scene_preview(tmp_path: Path) -> None:
    """Scene lane identity should keep unrelated scenes independent."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())
    scene_b = _preview_update(
        image="scene-b",
        scene_run_id="scene-run",
        scene_key="scene-b",
    )

    coalescer.submit_output_image(
        _output_update(
            tmp_path / "scene-a.png",
            scene_run_id="scene-run",
            scene_key="scene-a",
        )
    )
    coalescer.submit_preview(scene_b)

    assert coalescer.drain_all().preview_updates == (_live_preview(scene_b),)


def test_batch_final_closes_ambiguous_source_preview(tmp_path: Path) -> None:
    """A list item final should close less-specific previews for that source."""

    coalescer = GenerationFeedbackCoalescer()
    coalescer.submit_run_started(_run_started())

    coalescer.submit_output_image(_output_update(tmp_path / "item-0.png", list_index=0))
    coalescer.submit_preview(_preview_update(image="ambiguous"))

    assert coalescer.drain_all().preview_updates == ()
