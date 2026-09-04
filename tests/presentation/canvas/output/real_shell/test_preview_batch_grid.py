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

"""Verify streaming preview placement inside production batch grids."""

from __future__ import annotations

from uuid import UUID

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_same_run_tensor_batch_replaces_preview_with_both_final_members(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Show every final tensor member after one scene preview is superseded."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    scene = SceneSpec(
        run_id="scene-test-run",
        key="scene-1",
        title="Scene 1",
        order=0,
        count=3,
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene.run_id,
        workflow_id="workflow-alpha",
        workflow_name="Scene Test",
        scenes=((scene.key, scene.title, scene.order),),
    )
    run = harness.start_run(
        "alpha",
        output_session_id="scene-test-output-session",
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (220, 170, 35),
            scene=scene,
        ),
    )
    _flush_preview(harness)
    preview_ids = harness.fingerprint().presented_image_ids
    assert len(preview_ids) == 1

    harness.emit_output(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (190, 30, 40),
            batch_index=0,
            scene=scene,
        ),
    )
    harness.emit_output(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (30, 190, 40),
            batch_index=1,
            scene=scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)

    final_ids = harness.output_ids_for_scene_source(
        scene_key=scene.key,
        source_key="alpha:text",
    )
    presented = harness.fingerprint()
    assert len(final_ids) == 2
    assert tuple(frame[1] for frame in presented.grid_target_frames) == final_ids
    assert not set(preview_ids).intersection(presented.presented_image_ids)
    assert harness.shell.output_canvas.active_set_index == 0


def test_later_tensor_member_remains_visible_beside_first_slot_preview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep a finalized later batch index visible while index zero is previewing."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    scene = SceneSpec(
        run_id="scene-test-run",
        key="scene-1",
        title="Scene 1",
        order=0,
        count=3,
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene.run_id,
        workflow_id="workflow-alpha",
        workflow_name="Scene Test",
        scenes=((scene.key, scene.title, scene.order),),
    )
    run = harness.start_run(
        "alpha",
        output_session_id="scene-test-output-session",
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (220, 170, 35),
            scene=scene,
        ),
    )
    _flush_preview(harness)
    source_preview_id = next(
        lane.preview_id
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.source_key == "alpha:text" and lane.key.placement.value == "source"
    )

    harness.emit_output(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (30, 190, 40),
            batch_index=1,
            scene=scene,
        ),
    )
    harness.wait_for_output_count("alpha", 1)
    final_index_one_id = harness.output_ids("alpha")[0]
    harness.shell.output_image_pipeline.flush_visible_output_projection()
    harness.process_events()
    harness.wait_until(
        lambda: (
            tuple(frame[1] for frame in harness.fingerprint().grid_target_frames)
            == (source_preview_id, final_index_one_id)
        )
    )

    harness.emit_output(
        run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (190, 30, 40),
            batch_index=0,
            scene=scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(
        lambda: (
            len(
                _scene_source_ids(
                    harness,
                    scene_key=scene.key,
                    source_key="alpha:text",
                )
            )
            == 2
            and source_preview_id not in harness.fingerprint().presented_image_ids
        )
    )
    final_ids = harness.output_ids_for_scene_source(
        scene_key=scene.key,
        source_key="alpha:text",
    )
    assert (
        tuple(frame[1] for frame in harness.fingerprint().grid_target_frames)
        == final_ids
    )


def test_second_scene_tensor_batch_stays_all_and_updates_its_representative(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep Automatic on All after the second scene becomes presentable."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    scenes = tuple(
        SceneSpec(
            run_id="scene-test-run",
            key=f"scene-{index}",
            title=f"Scene {index}",
            order=index - 1,
            count=3,
        )
        for index in range(1, 4)
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id="scene-test-run",
        workflow_id="workflow-alpha",
        workflow_name="Scene Test",
        scenes=tuple((scene.key, scene.title, scene.order) for scene in scenes),
    )
    output_session_id = "scene-test-output-session"
    for run_index, scene in enumerate(scenes[:2], start=1):
        run = harness.start_run(
            "alpha",
            run_index=run_index,
            output_session_id=output_session_id,
            preview_source_keys=frozenset({"alpha:text"}),
        )
        harness.emit_preview(
            run,
            OutputSpec(
                "alpha:text",
                "Text to Image",
                (220, 170, 35),
                scene=scene,
            ),
        )
        _flush_preview(harness)
        for batch_index, color in enumerate(((190, 30, 40), (30, 190, 40))):
            harness.emit_output(
                run,
                OutputSpec(
                    "alpha:text",
                    "Text to Image",
                    color,
                    batch_index=batch_index,
                    scene=scene,
                ),
            )
        harness.wait_for_output_count("alpha", run_index * 2)
        harness.complete_run(run)

    harness.wait_until(
        lambda: any(
            scene.scene_key == "scene-2"
            for scene in getattr(
                harness.shell.output_canvas._output_projection,
                "scene_groups",
                (),
            )
        )
    )
    expected_ids = harness.output_ids_for_scene_source(
        scene_key="scene-2",
        source_key="alpha:text",
    )
    first_scene_ids = harness.output_ids_for_scene_source(
        scene_key="scene-1",
        source_key="alpha:text",
    )
    harness.wait_until(
        lambda: (
            harness.shell.output_canvas.active_scene_key == "scene-2"
            and harness.shell.output_canvas.active_scene_overview
            and harness.shell.output_canvas.active_source_key is None
            and harness.shell.output_canvas.active_set_index == 1
            and tuple(frame[1] for frame in harness.fingerprint().grid_target_frames)
            == (first_scene_ids[0], expected_ids[0])
        )
    )

    assert len(expected_ids) == 2


def test_new_run_preview_uses_next_grid_member_when_prior_result_exists(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep the prior queued-run result visible beside a streaming preview."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    output_session_id = "generate-click-1"
    finalized_ids = _seed_batched_text_outputs(
        harness,
        output_session_id=output_session_id,
        colors=((190, 30, 40),),
    )

    second_run = harness.start_run(
        "alpha",
        run_index=2,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        second_run,
        OutputSpec("alpha:text", "Text to Image", (220, 170, 35)),
    )
    _flush_preview(harness)

    source_preview = next(
        lane
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.source_key == "alpha:text" and lane.key.placement.value == "source"
    )
    streamed = harness.fingerprint()
    presented_ids = tuple(frame[1] for frame in streamed.grid_target_frames)
    assert len(streamed.grid_target_frames) == 2
    assert presented_ids == (
        finalized_ids[0],
        source_preview.preview_id,
    ), streamed
    assert harness.shell.output_canvas.active_set_index == 0

    harness.emit_preview(
        second_run,
        OutputSpec("alpha:text", "Text to Image", (225, 175, 40)),
    )
    _flush_preview(harness)

    refreshed = harness.fingerprint()
    assert tuple(frame[1] for frame in refreshed.grid_target_frames) == presented_ids
    assert harness.shell.output_canvas.active_set_index == 0


def test_batched_preview_updates_the_same_grid_selected_in_manual(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Refresh a manually selected source grid without changing its drill level."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    output_session_id = "generate-click-1"
    finalized_ids = _seed_batched_text_outputs(
        harness,
        output_session_id=output_session_id,
        colors=((190, 30, 40), (30, 190, 40)),
    )
    harness.select_output_set(0)
    assert (
        harness.fingerprint().workflow_output_focus_modes["workflow-alpha"] == "manual"
    )

    second_run = harness.start_run(
        "alpha",
        run_index=2,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        second_run,
        OutputSpec("alpha:text", "Text to Image", (220, 170, 35)),
    )
    _flush_preview(harness)

    source_preview = next(
        lane
        for lane in harness.shell.output_preview_registry.lanes_for_session_like()
        if lane.key.source_key == "alpha:text" and lane.key.placement.value == "source"
    )
    streamed = harness.fingerprint()
    assert tuple(frame[1] for frame in streamed.grid_target_frames) == (
        finalized_ids[0],
        finalized_ids[1],
        source_preview.preview_id,
    ), streamed
    assert harness.shell.output_canvas.active_set_index == 0
    assert streamed.workflow_output_focus_modes["workflow-alpha"] == "manual"


def _seed_batched_text_outputs(
    harness: RealShellOutputCanvasHarness,
    *,
    output_session_id: str,
    colors: tuple[tuple[int, int, int], ...],
) -> tuple[UUID, ...]:
    """Present one finalized Text to Image batch for preview-overlay tests."""

    run = harness.start_run(
        "alpha",
        run_index=1,
        output_session_id=output_session_id,
    )
    for batch_index, color in enumerate(colors):
        harness.emit_output(
            run,
            OutputSpec(
                "alpha:text",
                "Text to Image",
                color,
                batch_index=batch_index,
            ),
        )
    harness.wait_for_output_count("alpha", len(colors))
    if len(colors) > 1:
        harness.wait_until(
            lambda: len(harness.fingerprint().grid_target_frames) == len(colors)
        )
    else:
        harness.wait_until(lambda: len(harness.fingerprint().presented_image_ids) == 1)
    return harness.output_ids("alpha")


def _scene_source_ids(
    harness: RealShellOutputCanvasHarness,
    *,
    scene_key: str,
    source_key: str,
) -> tuple[UUID, ...]:
    """Return projected scene/source ids while tolerating a queued projection."""

    try:
        return harness.output_ids_for_scene_source(
            scene_key=scene_key,
            source_key=source_key,
        )
    except AssertionError:
        return ()


def _flush_preview(harness: RealShellOutputCanvasHarness) -> None:
    """Drain coalesced preview and deferred navigation work deterministically."""

    harness.process_events()
    harness.shell.generation_feedback_dispatcher.flush_now()
    harness.process_events()
    harness.process_events()
