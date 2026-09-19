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

"""Drive the complete three-scene Automatic-to-Manual Output story."""

from __future__ import annotations

from uuid import UUID

from tests.presentation.canvas.output.real_shell.automatic_scene_story_support import (
    TEXT_SOURCE,
    UPSCALE_SOURCE,
    assert_collapsed_all,
    assert_single_preview,
    emit_preview,
    emit_single_output,
    emit_tensor_batch_and_ids,
    observe_auto_state,
    scene_preview_id,
    source_preview_id,
    start_scene_test,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import GenerationRunHandle, SceneSpec


def prove_complete_automatic_scene_story(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Prove progressive batch replacement, All stability, and Manual ownership."""

    scenes = start_scene_test(harness)
    output_session_id = "scene-test-complete-story"
    first_run = _start_run(harness, output_session_id, 1)
    emit_preview(
        harness,
        first_run,
        scene=scenes[0],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        color=(45, 85, 180),
    )
    assert_single_preview(harness, source_key=TEXT_SOURCE)
    first_text_ids = emit_tensor_batch_and_ids(
        harness,
        first_run,
        scene=scenes[0],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        colors=((160, 45, 55), (55, 45, 170)),
        expected_output_count=0,
    )
    assert observe_auto_state(harness).mounted_grid_ids == first_text_ids
    emit_preview(
        harness,
        first_run,
        scene=scenes[0],
        source_key=UPSCALE_SOURCE,
        source_label="Diffusion Upscale",
        color=(55, 175, 105),
    )
    assert observe_auto_state(harness).mounted_grid_ids == (
        source_preview_id(harness, UPSCALE_SOURCE),
        first_text_ids[1],
    )
    output_count, first_upscale_zero = emit_single_output(
        harness,
        first_run,
        scene=scenes[0],
        source_key=UPSCALE_SOURCE,
        source_label="Diffusion Upscale",
        color=(45, 155, 85),
        batch_index=0,
        expected_output_count=2,
    )
    assert observe_auto_state(harness).mounted_grid_ids == (
        first_upscale_zero,
        first_text_ids[1],
    )
    output_count, first_upscale_one = emit_single_output(
        harness,
        first_run,
        scene=scenes[0],
        source_key=UPSCALE_SOURCE,
        source_label="Diffusion Upscale",
        color=(85, 45, 165),
        batch_index=1,
        expected_output_count=output_count,
    )
    assert observe_auto_state(harness).mounted_grid_ids == (
        first_upscale_zero,
        first_upscale_one,
    )
    harness.complete_run(first_run)

    scene_representatives: list[UUID] = [first_upscale_zero]
    for scene_number, scene in enumerate(scenes[1:], start=2):
        run = _start_run(harness, output_session_id, scene_number)
        emit_preview(
            harness,
            run,
            scene=scene,
            source_key=TEXT_SOURCE,
            source_label="Text to Image",
            color=(45, 80 + 15 * scene_number, 180),
        )
        assert_collapsed_all(
            harness,
            visible_ids=(*scene_representatives, scene_preview_id(harness, scene.key)),
        )
        text_ids = emit_tensor_batch_and_ids(
            harness,
            run,
            scene=scene,
            source_key=TEXT_SOURCE,
            source_label="Text to Image",
            colors=((170 - 10 * scene_number, 45, 55), (55, 45, 170)),
            expected_output_count=output_count,
        )
        output_count += 2
        assert_collapsed_all(
            harness,
            visible_ids=(*scene_representatives, text_ids[0]),
        )
        emit_preview(
            harness,
            run,
            scene=scene,
            source_key=UPSCALE_SOURCE,
            source_label="Diffusion Upscale",
            color=(55, 175, 90 + 5 * scene_number),
        )
        assert_collapsed_all(
            harness,
            visible_ids=(*scene_representatives, scene_preview_id(harness, scene.key)),
        )
        if scene_number == 3:
            _prove_manual_ownership(
                harness,
                run,
                scene,
                output_count=output_count,
                first_upscale_ids=(first_upscale_zero, first_upscale_one),
            )
            return
        upscale_ids = emit_tensor_batch_and_ids(
            harness,
            run,
            scene=scene,
            source_key=UPSCALE_SOURCE,
            source_label="Diffusion Upscale",
            colors=((45, 145, 85), (85, 55, 155)),
            expected_output_count=output_count,
        )
        output_count += 2
        scene_representatives.append(upscale_ids[0])
        assert_collapsed_all(harness, visible_ids=tuple(scene_representatives))
        harness.complete_run(run)


def _prove_manual_ownership(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    scene: SceneSpec,
    *,
    output_count: int,
    first_upscale_ids: tuple[UUID, UUID],
) -> None:
    """Drill from All and prove later generation events cannot steal focus."""

    harness.click_canvas_image(first_upscale_ids[0])
    manual_batch = observe_auto_state(harness)
    assert manual_batch.durable_route == (
        "scene-1",
        False,
        UPSCALE_SOURCE,
        0,
        None,
    )
    assert manual_batch.mounted_grid_ids == first_upscale_ids
    final_ids = emit_tensor_batch_and_ids(
        harness,
        run,
        scene=scene,
        source_key=UPSCALE_SOURCE,
        source_label="Diffusion Upscale",
        colors=((45, 135, 95), (95, 65, 145)),
        expected_output_count=output_count,
    )
    after_later_events = observe_auto_state(harness)
    assert after_later_events.durable_route == manual_batch.durable_route
    assert after_later_events.mounted_grid_ids == manual_batch.mounted_grid_ids
    assert (
        harness.fingerprint().workflow_output_focus_modes["workflow-alpha"] == "manual"
    )

    harness.click_canvas_image(first_upscale_ids[1])
    concrete = observe_auto_state(harness)
    assert concrete.durable_route == (
        "scene-1",
        False,
        UPSCALE_SOURCE,
        2,
        first_upscale_ids[1],
    )
    assert concrete.presented_ids == (first_upscale_ids[1],)
    harness.complete_run(run)
    assert len(final_ids) == 2
    assert harness.output_count("alpha") == 12
    assert harness.preview_count() == 0


def _start_run(
    harness: RealShellOutputCanvasHarness,
    output_session_id: str,
    run_index: int,
) -> GenerationRunHandle:
    """Start one scene request with both preview-capable CubeOutputs."""

    return harness.start_run(
        "alpha",
        run_index=run_index,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({TEXT_SOURCE, UPSCALE_SOURCE}),
    )


__all__ = ["prove_complete_automatic_scene_story"]
