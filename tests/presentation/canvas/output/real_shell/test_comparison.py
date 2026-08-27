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

"""Verify comparison identity, navigation, and resize transitions."""

from __future__ import annotations

from uuid import UUID

from cutecanvas import CanvasPresentationKind

from substitute.application.workflows.output_compare_state import (
    OutputCompareSelection,
    OutputCompareState,
)
from tests.presentation.canvas.output.real_shell.grid_support import (
    wait_for_new_grid_snapshot,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_restored_comparison_chrome_identifies_each_rendered_side(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Derive both comparison bars from the compositions rendered on their sides."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    expected_output_count = 0
    for scene_index in range(2):
        run = harness.start_run("alpha", run_index=scene_index + 1)
        scene = SceneSpec(
            run_id="scene-run-alpha",
            key=f"scene{scene_index + 1}",
            title=f"scene {scene_index + 1}",
            order=scene_index,
            count=2,
        )
        harness.emit_output(
            run,
            OutputSpec(
                "alpha:text",
                "Text to Image",
                (210, 40 + scene_index * 20, 40),
                scene=scene,
            ),
        )
        harness.emit_output(
            run,
            OutputSpec(
                "alpha:upscale",
                "Diffusion Upscale",
                (40, 40 + scene_index * 20, 210),
                scene=scene,
            ),
        )
        expected_output_count += 2
        if scene_index == 0:
            harness.emit_output(
                run,
                OutputSpec(
                    "alpha:text",
                    "Text to Image",
                    (180, 180, 40),
                    batch_index=1,
                    scene=scene,
                ),
            )
            expected_output_count += 1
        harness.wait_for_output_count("alpha", expected_output_count)
        harness.complete_run(run)
    harness.project_workflow_directly("alpha")
    scene1_text_ids = harness.output_ids_for_scene_source(
        scene_key="scene1",
        source_key="alpha:text",
    )
    scene1_upscale_id = harness.output_ids_for_scene_source(
        scene_key="scene1",
        source_key="alpha:upscale",
    )[0]
    scene2_upscale_id = harness.output_ids_for_scene_source(
        scene_key="scene2",
        source_key="alpha:upscale",
    )[0]
    harness.select_output_id(scene1_upscale_id)
    harness.wait_until(
        lambda: harness.fingerprint().active_image_id == scene1_upscale_id
    )
    workflow = harness.shell.workflow_session_service.workflows["workflow-alpha"]
    workflow.output_compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene1", 1, "alpha:text"),
        comparison=OutputCompareSelection("scene1", 1, "alpha:upscale"),
    )

    harness.project_workflow_directly("alpha")
    _assert_comparison_side_identity(
        harness,
        base_image_id=scene1_text_ids[0],
        comparison_image_id=scene1_upscale_id,
        base_rgb=(210, 40, 40),
        comparison_rgb=(40, 40, 210),
        base_labels=("scene 1", "1", "Text to Image"),
        comparison_labels=("scene 1", "1", "Diffusion Upscale"),
        base_batch_visible=True,
        comparison_batch_visible=True,
    )

    workflow.output_compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene1", 2, "alpha:text"),
        comparison=OutputCompareSelection("scene2", 1, "alpha:upscale"),
    )
    harness.project_workflow_directly("alpha")
    _assert_comparison_side_identity(
        harness,
        base_image_id=scene1_text_ids[1],
        comparison_image_id=scene2_upscale_id,
        base_rgb=(180, 180, 40),
        comparison_rgb=(40, 60, 210),
        base_labels=("scene 1", "2", "Text to Image"),
        comparison_labels=("scene 2", "1", "Diffusion Upscale"),
        base_batch_visible=True,
        comparison_batch_visible=False,
    )


def test_batchless_comparison_exposes_scene_navigation_on_both_sides(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Comparison chrome should expose multiple scenes without requiring batches."""

    harness.add_workflow("alpha", activate=True)
    harness.show_canvas("Output")
    run = harness.start_run("alpha")
    for scene_index, color in enumerate(((190, 50, 40), (40, 50, 190)), start=1):
        harness.emit_output(
            run,
            OutputSpec(
                "alpha:text",
                "Text to Image",
                color,
                scene=SceneSpec(
                    run_id="scene-run-alpha",
                    key=f"scene{scene_index}",
                    title=f"scene {scene_index}",
                    order=scene_index - 1,
                    count=2,
                ),
            ),
        )
    harness.wait_for_output_count("alpha", 2)
    harness.complete_run(run)
    workflow = harness.shell.workflow_session_service.workflows["workflow-alpha"]
    workflow.output_compare_state = OutputCompareState(
        enabled=True,
        base=OutputCompareSelection("scene1", 1, "alpha:text"),
        comparison=OutputCompareSelection("scene2", 1, "alpha:text"),
    )

    harness.project_workflow_directly("alpha")
    canvas = harness.shell.output_canvas
    harness.wait_until(lambda: canvas.comparison_nav_container.isVisibleTo(canvas))

    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert canvas.comparison_scene_selector_button.isVisibleTo(canvas)
    assert not canvas.scene_selector_button.visibleRegion().isEmpty()
    assert not canvas.comparison_scene_selector_button.visibleRegion().isEmpty()
    assert not canvas.set_selector_button.isVisibleTo(canvas)
    assert not canvas.comparison_set_selector_button.isVisibleTo(canvas)


def _assert_comparison_side_identity(
    harness: RealShellOutputCanvasHarness,
    *,
    base_image_id: UUID,
    comparison_image_id: UUID,
    base_rgb: tuple[int, int, int],
    comparison_rgb: tuple[int, int, int],
    base_labels: tuple[str, str, str],
    comparison_labels: tuple[str, str, str],
    base_batch_visible: bool,
    comparison_batch_visible: bool,
) -> None:
    """Assert that pixels, targets, and chrome identify the same two sides."""

    canvas = harness.shell.output_canvas
    harness.wait_until(
        lambda: (
            canvas.document.session.presentation.kind
            is CanvasPresentationKind.COMPARISON
        )
    )
    presentation = canvas.document.session.presentation
    assert canvas.document.image_ids_for_compositions(presentation.target_ids) == (
        base_image_id,
        comparison_image_id,
    )

    def rendered_side_colors() -> tuple[
        tuple[int, int, int],
        tuple[int, int, int],
    ]:
        """Sample one stable interior pixel from each comparison side."""

        comparison = canvas.workspace.currentCanvas()
        assert comparison is not None
        frame = comparison.grab().toImage()
        left = frame.pixelColor(frame.width() // 4, frame.height() // 2)
        right = frame.pixelColor(frame.width() * 3 // 4, frame.height() // 2)
        return (
            (left.red(), left.green(), left.blue()),
            (right.red(), right.green(), right.blue()),
        )

    harness.wait_until(lambda: rendered_side_colors() == (base_rgb, comparison_rgb))
    assert (
        canvas.scene_selector_button.text(),
        canvas.set_selector_button.text(),
        canvas.source_selector_button.text(),
    ) == base_labels
    assert (
        canvas.comparison_scene_selector_button.text(),
        canvas.comparison_set_selector_button.text(),
        canvas.comparison_source_selector_button.text(),
    ) == comparison_labels
    assert canvas.scene_selector_button.isVisibleTo(canvas)
    assert canvas.comparison_scene_selector_button.isVisibleTo(canvas)
    assert canvas.set_selector_button.isVisibleTo(canvas) is base_batch_visible
    assert (
        canvas.comparison_set_selector_button.isVisibleTo(canvas)
        is comparison_batch_visible
    )
    assert canvas.source_selector_button.isVisibleTo(canvas)
    assert canvas.comparison_source_selector_button.isVisibleTo(canvas)


def test_scene_preview_to_final_during_resize_keeps_final_grid_content(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A final should replace its live scene tile while resize work is pending."""

    harness.add_workflow("alpha", activate=True)
    run = harness.start_run("alpha")
    first_scene = SceneSpec("scene-run", "scene-1", "Scene 1", 0, 2)
    second_scene = SceneSpec("scene-run", "scene-2", "Scene 2", 1, 2)
    harness.emit_output(
        run,
        OutputSpec("scene-one", "Scene One", (190, 50, 40), scene=first_scene),
    )
    harness.emit_output(
        run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 50, 120),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 2)
    preview_run = harness.start_run("alpha", run_index=2)
    harness.emit_preview(
        preview_run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 190, 50),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_preview_count(1)
    workspace = harness.shell.output_canvas.workspace
    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(420.0, 1000.0)
    wait_for_new_grid_snapshot(harness, previous_snapshot)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    preview_grid = harness.fingerprint()
    assert set(preview_grid.preview_image_ids).intersection(
        placement[1] for placement in preview_grid.grid_target_frames
    )

    previous_snapshot = workspace.gridSnapshot()
    harness.set_output_viewport_extent(1200.0, 420.0)
    wait_for_new_grid_snapshot(harness, previous_snapshot)
    harness.emit_output(
        preview_run,
        OutputSpec(
            "scene-one",
            "Scene One",
            (40, 50, 190),
            list_index=1,
            scene=second_scene,
        ),
    )
    harness.wait_for_output_count("alpha", 3)
    harness.wait_for_preview_count(0)
    harness.wait_until(lambda: len(harness.fingerprint().grid_target_frames) == 2)
    final_grid = harness.fingerprint()

    final_image_ids = {placement[1] for placement in final_grid.grid_target_frames}
    assert final_image_ids <= set(harness.output_ids("alpha"))
    assert not set(preview_grid.preview_image_ids).intersection(final_image_ids)
