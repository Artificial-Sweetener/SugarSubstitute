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

"""Prove the real batched multi-scene Automatic story in the mounted shell."""

from __future__ import annotations

from tests.presentation.canvas.output.real_shell.automatic_scene_complete_story import (
    prove_complete_automatic_scene_story,
)
from tests.presentation.canvas.output.real_shell.automatic_scene_story_support import (
    TEXT_SOURCE,
    UPSCALE_SOURCE,
    emit_preview,
    emit_tensor_batch_and_ids,
    observe_auto_state,
    scene_preview_id,
    source_preview_id,
    start_scene_test,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness


def test_scene_one_upscale_preview_preserves_second_text_batch_member(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Replace only slot zero when a later CubeOutput begins previewing."""

    scenes = start_scene_test(harness)
    run = harness.start_run(
        "alpha",
        run_index=1,
        output_session_id="scene-test-cross-cube",
        preview_source_keys=frozenset({TEXT_SOURCE, UPSCALE_SOURCE}),
    )
    emit_preview(
        harness,
        run,
        scene=scenes[0],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        color=(45, 85, 180),
    )
    lone_preview = observe_auto_state(harness)
    text_ids = emit_tensor_batch_and_ids(
        harness,
        run,
        scene=scenes[0],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        colors=((160, 45, 55), (55, 45, 170)),
        expected_output_count=0,
    )
    text_batch = observe_auto_state(harness)
    emit_preview(
        harness,
        run,
        scene=scenes[0],
        source_key=UPSCALE_SOURCE,
        source_label="Diffusion Upscale",
        color=(55, 175, 105),
    )
    upscale_preview_id = source_preview_id(harness, UPSCALE_SOURCE)
    upscale_preview = observe_auto_state(harness)

    assert lone_preview.visible_route == ("scene-1", False, TEXT_SOURCE, 1)
    assert len(lone_preview.presented_ids) == 1
    assert text_batch.visible_route == ("scene-1", False, TEXT_SOURCE, 0)
    assert text_batch.mounted_grid_ids == text_ids
    assert upscale_preview.mounted_grid_ids == (upscale_preview_id, text_ids[1]), (
        "Cross-Cube preview replaced the complete canvas instead of slot zero",
        upscale_preview,
    )
    assert upscale_preview.visible_route == (
        "scene-1",
        False,
        UPSCALE_SOURCE,
        0,
    )


def test_automatic_stays_all_after_second_scene_becomes_presentable(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Never drill Automatic out of All after two scenes have visible content."""

    scenes = start_scene_test(harness)
    output_session_id = "scene-test-auto-all"
    first_run = harness.start_run(
        "alpha",
        run_index=1,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({TEXT_SOURCE}),
    )
    first_scene_ids = emit_tensor_batch_and_ids(
        harness,
        first_run,
        scene=scenes[0],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        colors=((160, 45, 55), (55, 45, 170)),
        expected_output_count=0,
    )
    harness.complete_run(first_run)
    second_run = harness.start_run(
        "alpha",
        run_index=2,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({TEXT_SOURCE}),
    )
    emit_preview(
        harness,
        second_run,
        scene=scenes[1],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        color=(45, 100, 180),
    )
    second_preview_id = scene_preview_id(harness, scenes[1].key)
    second_preview = observe_auto_state(harness)
    second_scene_ids = emit_tensor_batch_and_ids(
        harness,
        second_run,
        scene=scenes[1],
        source_key=TEXT_SOURCE,
        source_label="Text to Image",
        colors=((150, 55, 65), (65, 55, 160)),
        expected_output_count=2,
    )
    second_batch = observe_auto_state(harness)

    assert second_preview.visible_route == (scenes[1].key, True, None, 1)
    assert second_preview.mounted_grid_ids == (
        first_scene_ids[0],
        second_preview_id,
    )
    assert second_batch.visible_route == (scenes[1].key, True, None, 1), (
        "Automatic drilled out of All when Scene 2's batch arrived",
        second_batch,
    )
    assert second_batch.durable_route == (None, True, None, 1, None)
    assert second_batch.mounted_grid_ids == (
        first_scene_ids[0],
        second_scene_ids[0],
    )


def test_automatic_three_scene_story_progressively_replaces_then_stays_all(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Prove the complete Auto timeline and Manual ownership handoff."""

    prove_complete_automatic_scene_story(harness)
