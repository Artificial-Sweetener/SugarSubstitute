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

"""Regress reported multi-scene tensor-batch and mounted click failures."""

from __future__ import annotations

from uuid import UUID

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import (
    GenerationRunHandle,
    OutputSpec,
    SceneSpec,
)

_OUTPUT_SESSION_ID = "scene-test-click"
_SCENE_RUN_ID = "scene-test-scenes"
_TEXT_SOURCE = "alpha:text"
_UPSCALE_SOURCE = "alpha:upscale"


def test_same_run_batch_preview_keeps_later_member_until_both_finals_arrive(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep batch index one beside the preview, then present both final members."""

    scenes = _start_scene_test(harness)
    run = _start_scene_run(harness, run_index=1)
    harness.emit_preview(
        run,
        OutputSpec(
            _TEXT_SOURCE,
            "Text to Image",
            (40, 140, 180),
            scene=scenes[0],
        ),
    )
    _flush_preview(harness)
    preview_id = _source_preview_id(harness, source_key=_TEXT_SOURCE)

    harness.emit_output(
        run,
        OutputSpec(
            _TEXT_SOURCE,
            "Text to Image",
            (60, 180, 80),
            batch_index=1,
            scene=scenes[0],
        ),
    )
    harness.wait_for_output_count("alpha", 1)
    later_member_id = harness.output_ids("alpha")[0]
    harness.shell.output_image_pipeline.flush_visible_output_projection()
    harness.process_events()
    harness.wait_until(
        lambda: _mounted_grid_ids(harness) == (preview_id, later_member_id)
    )

    harness.emit_output(
        run,
        OutputSpec(
            _TEXT_SOURCE,
            "Text to Image",
            (180, 60, 80),
            batch_index=0,
            scene=scenes[0],
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(
        lambda: (
            len(_scene_source_ids(harness, scenes[0], _TEXT_SOURCE)) == 2
            and preview_id not in harness.fingerprint().presented_image_ids
        )
    )

    final_ids = _scene_source_ids(harness, scenes[0], _TEXT_SOURCE)
    state = harness.fingerprint()
    assert len(final_ids) == 2
    assert _mounted_grid_ids(harness) == final_ids
    assert state.workflow_output_routes["workflow-alpha"] == (
        "scene-1",
        False,
        _TEXT_SOURCE,
        0,
        None,
    )
    assert state.workflow_output_focus_modes["workflow-alpha"] == "automatic"


def test_mounted_clicks_drill_all_to_scene_batch_to_concrete_output(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Drill All to a full tensor batch and then to one concrete output."""

    scenes = _start_scene_test(harness)
    scene_batches: dict[str, tuple[UUID, ...]] = {}
    expected_output_count = 0
    for run_index, scene in enumerate(scenes, start=1):
        run = _start_scene_run(harness, run_index=run_index)
        expected_output_count = _emit_tensor_batch(
            harness,
            run,
            scene=scene,
            source_key=_TEXT_SOURCE,
            source_label="Text to Image",
            colors=((170, 55, 65), (65, 55, 170)),
            expected_output_count=expected_output_count,
        )
        expected_output_count = _emit_tensor_batch(
            harness,
            run,
            scene=scene,
            source_key=_UPSCALE_SOURCE,
            source_label="Diffusion Upscale",
            colors=((55, 170, 85), (85, 55, 170)),
            expected_output_count=expected_output_count,
        )
        scene_batches[scene.key] = _scene_source_ids(
            harness,
            scene,
            _UPSCALE_SOURCE,
        )
        assert len(scene_batches[scene.key]) == 2
        harness.complete_run(run)

    harness.select_output_scene("all")
    all_state = harness.fingerprint()
    assert all_state.workflow_output_routes["workflow-alpha"] == (
        None,
        True,
        None,
        1,
        None,
    )
    assert len(all_state.presented_image_ids) == 3
    scene_one_representative = scene_batches["scene-1"][0]
    assert scene_one_representative in all_state.presented_image_ids

    harness.click_canvas_image(scene_one_representative)
    batch_state = harness.fingerprint()
    assert batch_state.workflow_output_routes["workflow-alpha"] == (
        "scene-1",
        False,
        _UPSCALE_SOURCE,
        0,
        None,
    )
    assert _mounted_grid_ids(harness) == scene_batches["scene-1"]

    selected_id = scene_batches["scene-1"][1]
    harness.click_canvas_image(selected_id)
    concrete_state = harness.fingerprint()
    assert concrete_state.workflow_output_routes["workflow-alpha"] == (
        "scene-1",
        False,
        _UPSCALE_SOURCE,
        2,
        selected_id,
    )
    assert concrete_state.presented_image_ids == (selected_id,)


def _start_scene_test(
    harness: RealShellOutputCanvasHarness,
) -> tuple[SceneSpec, ...]:
    """Mount Scene Test and register its three-scene run."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    scenes = tuple(
        SceneSpec(
            run_id=_SCENE_RUN_ID,
            key=f"scene-{scene_number}",
            title=f"Scene {scene_number}",
            order=scene_number - 1,
            count=3,
        )
        for scene_number in range(1, 4)
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=_SCENE_RUN_ID,
        workflow_id="workflow-alpha",
        workflow_name="Scene Test",
        scenes=tuple((scene.key, scene.title, scene.order) for scene in scenes),
    )
    return scenes


def _start_scene_run(
    harness: RealShellOutputCanvasHarness,
    *,
    run_index: int,
) -> GenerationRunHandle:
    """Start one Comfy request whose artifacts carry tensor batch indices."""

    return harness.start_run(
        "alpha",
        run_index=run_index,
        output_session_id=_OUTPUT_SESSION_ID,
        preview_source_keys=frozenset({_TEXT_SOURCE, _UPSCALE_SOURCE}),
    )


def _emit_tensor_batch(
    harness: RealShellOutputCanvasHarness,
    run: GenerationRunHandle,
    *,
    scene: SceneSpec,
    source_key: str,
    source_label: str,
    colors: tuple[tuple[int, int, int], tuple[int, int, int]],
    expected_output_count: int,
) -> int:
    """Emit two final artifacts from one source under one run identity."""

    for batch_index, color in enumerate(colors):
        harness.emit_output(
            run,
            OutputSpec(
                source_key,
                source_label,
                color,
                batch_index=batch_index,
                scene=scene,
            ),
        )
    expected_output_count += len(colors)
    harness.wait_for_output_count("alpha", expected_output_count)
    harness.wait_until(
        lambda: len(_scene_source_ids(harness, scene, source_key)) == len(colors)
    )
    return expected_output_count


def _source_preview_id(
    harness: RealShellOutputCanvasHarness,
    *,
    source_key: str,
) -> UUID:
    """Return the mounted source-lane preview identifier."""

    return next(
        lane.preview_id
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.source_key == source_key and lane.key.placement.value == "source"
    )


def _scene_source_ids(
    harness: RealShellOutputCanvasHarness,
    scene: SceneSpec,
    source_key: str,
) -> tuple[UUID, ...]:
    """Return projected scene/source IDs while projection work is queued."""

    try:
        return harness.output_ids_for_scene_source(
            scene_key=scene.key,
            source_key=source_key,
        )
    except AssertionError:
        return ()


def _mounted_grid_ids(harness: RealShellOutputCanvasHarness) -> tuple[UUID, ...]:
    """Return mounted image IDs in visual grid order."""

    return tuple(frame[1] for frame in harness.fingerprint().grid_target_frames)


def _flush_preview(harness: RealShellOutputCanvasHarness) -> None:
    """Drain coalesced preview and deferred navigation work deterministically."""

    harness.process_events()
    harness.shell.generation_feedback_dispatcher.flush_now()
    harness.process_events()
    harness.process_events()
