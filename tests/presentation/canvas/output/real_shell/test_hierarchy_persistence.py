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

"""Verify Output hierarchy routes survive workflow and canvas transitions."""

from __future__ import annotations


from tests.presentation.canvas.output.real_shell.hierarchy_support import (
    _assert_route,
    _enter_source_grid,
    _seed_sources,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


def test_source_grid_workflow_association_survives_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Mouse-selected workflow tabs restore their own Output source routes."""

    alpha_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:upscale", alpha_ids["alpha:upscale"])
    beta_ids = _seed_sources(harness, "beta", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "beta:text", beta_ids["beta:text"])

    harness.click_workflow_tab("alpha")
    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=0,
        image_id=None,
        visible_ids=alpha_ids["alpha:upscale"],
    )
    harness.click_workflow_tab("beta")
    _assert_route(
        harness,
        alias="beta",
        source_key="beta:text",
        set_index=0,
        image_id=None,
        visible_ids=beta_ids["beta:text"],
    )


def test_single_source_grid_route_survives_workflow_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A one-tile All Batches route should persist across workflow activation."""

    alpha_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 1})
    _enter_source_grid(harness, "alpha:text", alpha_ids["alpha:text"])
    harness.click_output_source_tab("alpha:upscale")
    beta_ids = _seed_sources(harness, "beta", {"text": 2})
    _enter_source_grid(harness, "beta:text", beta_ids["beta:text"])

    harness.activate_workflow("alpha")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=0,
        image_id=None,
        visible_ids=alpha_ids["alpha:upscale"],
    )


def test_first_new_session_result_resets_old_manual_source_grid(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """First new-session content should replace navigation over the prior result."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    scene_run_id = "scene-run-alpha-next"
    run = harness.start_run(
        "alpha",
        run_index=4,
        output_session_id=scene_run_id,
    )
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.emit_output(
        run,
        OutputSpec(
            "alpha:other",
            "Other",
            (80, 90, 100),
            scene=SceneSpec(
                run_id=scene_run_id,
                key="next-scene1",
                title="next-scene1",
                order=0,
                count=3,
            ),
        ),
    )
    harness.wait_for_output_count("alpha", 1)
    harness.wait_until(
        lambda: (
            harness.fingerprint().workflow_output_focus_modes["workflow-alpha"]
            == "automatic"
        )
    )
    harness.wait_until(lambda: bool(harness.fingerprint().presented_image_ids))

    fingerprint = harness.fingerprint()
    assert fingerprint.workflow_output_routes["workflow-alpha"] != (
        "scene3",
        False,
        "alpha:text",
        0,
        None,
    )
    assert fingerprint.active_source_tab_key != "alpha:text"
    assert set(fingerprint.presented_image_ids).isdisjoint(source_ids["alpha:text"])


def test_concrete_batch_source_route_survives_workflow_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A concrete Scene, Batch, and Cube-output route remains workflow-owned."""

    alpha_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:text", alpha_ids["alpha:text"])
    harness.click_canvas_image(alpha_ids["alpha:text"][1])
    harness.click_output_source_tab("alpha:upscale")
    beta_ids = _seed_sources(harness, "beta", {"text": 2})
    _enter_source_grid(harness, "beta:text", beta_ids["beta:text"])

    harness.activate_workflow("alpha")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=2,
        image_id=alpha_ids["alpha:upscale"][1],
        visible_ids=(alpha_ids["alpha:upscale"][1],),
    )


def test_scene_overview_route_survives_workflow_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """The all-scenes level restores with only the owning workflow's images."""

    alpha_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 1})
    alpha_workflow_id = harness.workflows["alpha"].workflow_id
    alpha_overview_ids = {
        placement[1] for placement in harness.fingerprint().grid_target_frames
    }
    assert len(alpha_overview_ids) == 3
    beta_ids = _seed_sources(harness, "beta", {"text": 2, "upscale": 1})
    _enter_source_grid(harness, "beta:text", beta_ids["beta:text"])

    harness.activate_workflow("alpha")

    fingerprint = harness.fingerprint()
    alpha_workflow_ids = set(fingerprint.workflow_output_image_ids[alpha_workflow_id])
    assert alpha_overview_ids <= alpha_workflow_ids
    assert set(fingerprint.presented_image_ids) == alpha_overview_ids, fingerprint
    assert fingerprint.workflow_output_routes[alpha_workflow_id][1] is True, fingerprint
    assert fingerprint.active_image_id is None, fingerprint
    assert set(alpha_ids["alpha:text"]) <= alpha_workflow_ids


def test_source_grid_survives_canvas_mode_round_trip(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Leaving Output canvas and returning preserves its source-grid route."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:upscale", source_ids["alpha:upscale"])

    harness.show_canvas("Input")
    harness.show_canvas("Output")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:upscale"],
    )


def test_concrete_batch_survives_canvas_mode_round_trip(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Leaving Output canvas and returning preserves its exact batch route."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.click_canvas_image(source_ids["alpha:text"][1])
    harness.click_output_source_tab("alpha:upscale")

    harness.show_canvas("Input")
    harness.show_canvas("Output")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=2,
        image_id=source_ids["alpha:upscale"][1],
        visible_ids=(source_ids["alpha:upscale"][1],),
    )
