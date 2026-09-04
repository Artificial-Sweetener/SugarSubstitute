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

"""Verify temporal Auto behavior while scene previews become presentable."""

from __future__ import annotations

from unittest.mock import patch

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_new_run_keeps_prior_result_presented_until_first_new_visual(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep the completed run visible while its replacement has no pixels yet."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    prior_run = harness.start_run(
        "alpha",
        run_index=1,
        output_session_id="prior-session",
    )
    harness.emit_output(
        prior_run,
        OutputSpec("alpha:text", "Text to Image", (120, 45, 180)),
    )
    harness.wait_for_output_count("alpha", 1)
    before = harness.fingerprint()

    harness.start_run(
        "alpha",
        run_index=2,
        output_session_id="replacement-session",
        preview_source_keys=frozenset({"alpha:text"}),
    )

    waiting = harness.fingerprint()
    assert waiting.presented_image_ids == before.presented_image_ids
    assert waiting.active_image_id == before.active_image_id
    assert waiting.active_image_rgb == before.active_image_rgb


def test_final_commit_keeps_preview_presented_until_final_projection(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep preview pixels mounted while asynchronous final projection is pending."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    run = harness.start_run(
        "alpha",
        output_session_id="generate-click-1",
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        run,
        OutputSpec("alpha:text", "Text to Image", (210, 40, 70)),
    )
    _flush_preview(harness)
    preview = harness.fingerprint()
    scheduler = harness.shell.output_image_pipeline._projection_scheduler

    with patch.object(scheduler, "request_projection"):
        harness.emit_output(
            run,
            OutputSpec("alpha:text", "Text to Image", (35, 90, 195)),
        )
        harness.wait_until(
            lambda: harness.output_count("alpha") == 1 and harness.preview_count() == 0
        )

        awaiting_projection = harness.fingerprint()
        assert awaiting_projection.presented_image_ids == preview.presented_image_ids
        assert awaiting_projection.active_image_rgb == (210, 40, 70)

    harness.project_workflow_directly("alpha")
    harness.wait_until(lambda: harness.fingerprint().active_image_rgb == (35, 90, 195))
    projected = harness.fingerprint()
    assert not set(preview.presented_image_ids) & set(projected.document_image_ids)


def test_first_scene_preview_does_not_expose_all_scene_navigation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Base scene navigation on presentable scenes rather than the generation plan."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    output_session_id = "generate-click-1"
    scene = SceneSpec(
        run_id="scene-run-1",
        key="scene-1",
        title="Scene 1",
        order=0,
        count=3,
    )
    run = harness.start_run(
        "alpha",
        output_session_id=output_session_id,
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene.run_id,
        workflow_id="workflow-alpha",
        workflow_name="alpha",
        scenes=(
            ("scene-1", "Scene 1", 0),
            ("scene-2", "Scene 2", 1),
            ("scene-3", "Scene 3", 2),
        ),
    )

    harness.emit_preview(
        run,
        OutputSpec("alpha:text", "Text to Image", (210, 40, 70), scene=scene),
    )
    _flush_preview(harness)

    canvas = harness.shell.output_canvas
    state = harness.fingerprint()
    assert canvas.scene_count == 1
    assert canvas.active_scene_key == "scene-1"
    assert canvas.active_scene_overview is False
    assert state.scene_selector_hidden is True
    assert not canvas.scene_selector_button.isVisibleTo(canvas)


def test_downstream_preview_replaces_first_text_grid_slot_in_auto(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Keep the second Text batch member while Upscale begins previewing."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    output_session_id = "generate-click-1"
    scene = SceneSpec(
        run_id="scene-run-1",
        key="scene-1",
        title="Scene 1",
        order=0,
        count=3,
    )
    run = harness.start_run(
        "alpha",
        output_session_id=output_session_id,
        preview_source_keys=frozenset({"alpha:text", "alpha:upscale"}),
    )
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene.run_id,
        workflow_id="workflow-alpha",
        workflow_name="alpha",
        scenes=(
            ("scene-1", "Scene 1", 0),
            ("scene-2", "Scene 2", 1),
            ("scene-3", "Scene 3", 2),
        ),
    )
    for batch_index, color in enumerate(((190, 30, 40), (160, 25, 35))):
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
    harness.wait_for_output_count("alpha", 2)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    before_upscale = harness.fingerprint()
    assert before_upscale.active_source_tab_key == "alpha:text"
    assert before_upscale.workflow_output_focus_modes["workflow-alpha"] == "automatic"

    harness.emit_preview(
        run,
        OutputSpec(
            "alpha:upscale",
            "Diffusion Upscale",
            (35, 185, 90),
            scene=scene,
        ),
    )
    _flush_preview(harness)

    followed = harness.fingerprint()
    canvas = harness.shell.output_canvas
    assert followed.active_source_tab_key == "alpha:upscale"
    assert followed.active_image_rgb is None
    assert len(followed.grid_target_frames) == 2
    assert (
        tuple(frame[1] for frame in followed.grid_target_frames)[1]
        == (
            harness.output_ids_for_scene_source(
                scene_key=scene.key,
                source_key="alpha:text",
            )[1]
        )
    )
    assert canvas.active_set_index == 0
    assert canvas.source_selector_button.text() == "Diffusion Upscale"
    assert followed.workflow_output_focus_modes["workflow-alpha"] == "automatic"


def test_second_scene_preview_promotes_auto_to_all_scene_overview(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Promote to All as soon as a second scene has presentable preview pixels."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    output_session_id = "generate-click-1"
    scene_run_id = "scene-run-1"
    harness.shell.output_scene_run_service.start_scene_run(
        scene_run_id=scene_run_id,
        workflow_id="workflow-alpha",
        workflow_name="alpha",
        scenes=(
            ("scene-1", "Scene 1", 0),
            ("scene-2", "Scene 2", 1),
            ("scene-3", "Scene 3", 2),
        ),
    )
    first_run = harness.start_run(
        "alpha",
        run_index=1,
        output_session_id=output_session_id,
    )
    harness.emit_output(
        first_run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (190, 35, 45),
            scene=SceneSpec(
                run_id=scene_run_id,
                key="scene-1",
                title="Scene 1",
                order=0,
                count=3,
            ),
        ),
    )
    harness.wait_for_output_count("alpha", 1)

    second_run = harness.start_run(
        "alpha",
        run_index=2,
        output_session_id=output_session_id,
        preview_source_keys=frozenset({"alpha:text"}),
    )
    harness.emit_preview(
        second_run,
        OutputSpec(
            "alpha:text",
            "Text to Image",
            (35, 90, 195),
            scene=SceneSpec(
                run_id=scene_run_id,
                key="scene-2",
                title="Scene 2",
                order=1,
                count=3,
            ),
        ),
    )
    _flush_preview(harness)

    canvas = harness.shell.output_canvas
    state = harness.fingerprint()
    assert canvas.scene_count == 2
    assert canvas.active_scene_overview is True
    assert state.scene_selector_hidden is False
    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert len(state.grid_target_frames) == 2
    assert state.workflow_output_focus_modes["workflow-alpha"] == "automatic"


def _flush_preview(harness: RealShellOutputCanvasHarness) -> None:
    """Drain coalesced preview and deferred navigation work deterministically."""

    harness.process_events()
    harness.shell.generation_feedback_dispatcher.flush_now()
    harness.process_events()
    harness.process_events()
