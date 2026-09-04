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

"""Verify scene, batch, and source navigation through the real Output hierarchy."""

from __future__ import annotations


from tests.presentation.canvas.output.real_shell.hierarchy_support import (
    _assert_route,
    _enter_source_grid,
    _seed_sources,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness


def test_batchless_scenes_show_scene_navigation_without_batch_navigation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Multiple scenes should expose scene navigation without a batch control."""

    source_ids = _seed_sources(harness, "alpha", {"text": 1})

    overview = harness.fingerprint()
    assert overview.workflow_output_routes[harness.workflows["alpha"].workflow_id][1]
    assert not overview.scene_selector_hidden, overview
    assert overview.set_selector_hidden, overview
    assert not overview.navigation_container_hidden, overview

    harness.click_canvas_image(harness.output_representative_id_for_scene("scene3"))
    harness.wait_until(
        lambda: (
            harness.fingerprint().workflow_output_routes[
                harness.workflows["alpha"].workflow_id
            ][:2]
            == ("scene3", False)
        )
    )

    scene = harness.fingerprint()
    assert not scene.scene_selector_hidden, scene
    assert scene.set_selector_hidden, scene
    assert not scene.navigation_container_hidden, scene
    assert set(scene.presented_image_ids) == set(source_ids["alpha:text"]), scene


def test_batched_scenes_show_only_available_hierarchy_controls(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Automatic scene overview should expose only scene-level navigation."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2})

    scene = harness.fingerprint()
    assert scene.workflow_output_routes[harness.workflows["alpha"].workflow_id] == (
        None,
        True,
        None,
        1,
        None,
    )
    assert not scene.scene_selector_hidden, scene
    assert scene.set_selector_hidden, scene
    assert not scene.navigation_container_hidden, scene
    assert len(scene.presented_image_ids) == 3, scene
    assert source_ids["alpha:text"][0] in scene.presented_image_ids, scene


def test_multi_image_source_tab_restores_grid_after_deferred_disjoint_switch(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Returning after the old grid is destroyed must remount retained targets."""

    source_ids = _seed_sources(harness, "alpha", {"text": 3, "upscale": 3})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.click_output_source_tab("alpha:upscale")
    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:upscale"],
    )

    harness.click_output_source_tab("alpha:text")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:text",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:text"],
    )
    harness.assert_document_targets_rendered(
        {
            source_ids["alpha:text"][0]: (40, 40, 120),
            source_ids["alpha:text"][1]: (40, 110, 120),
            source_ids["alpha:text"][2]: (40, 180, 120),
        }
    )


def test_multi_image_source_switch_preserves_all_batches_grid(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Switching between batched sources should remain at All Batches."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])

    harness.click_output_source_tab("alpha:upscale")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:upscale"],
    )
    harness.assert_document_targets_rendered(
        {
            source_ids["alpha:upscale"][0]: (130, 40, 120),
            source_ids["alpha:upscale"][1]: (130, 110, 120),
        }
    )


def test_source_switch_preserves_exact_concrete_batch_when_available(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A Cube-output switch inside a batch should retain the batch index."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.click_canvas_image(source_ids["alpha:text"][1])

    harness.click_output_source_tab("alpha:upscale")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:upscale",
        set_index=2,
        image_id=source_ids["alpha:upscale"][1],
        visible_ids=(source_ids["alpha:upscale"][1],),
    )


def test_missing_batch_source_switch_keeps_tab_and_route_consistent(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """An unavailable batch must preserve the exact current tab and route."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 1})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.click_canvas_image(source_ids["alpha:text"][1])

    harness.click_output_source_tab("alpha:upscale")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:text",
        set_index=2,
        image_id=source_ids["alpha:text"][1],
        visible_ids=(source_ids["alpha:text"][1],),
    )
