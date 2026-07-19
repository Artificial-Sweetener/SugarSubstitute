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

"""Abuse Output hierarchy and workflow ownership through rendered controls."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
import os
from pathlib import Path
from uuid import UUID

import pytest

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real Output QPane abuse matrix requires non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[RealShellOutputCanvasHarness]:
    """Create and close a real-shell Output canvas harness."""

    shell_harness = RealShellOutputCanvasHarness(output_root=tmp_path)
    try:
        yield shell_harness
    finally:
        shell_harness.close()


def test_single_image_source_tab_preserves_all_batches_level(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A source switch at All Batches must not drill into batch one."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 1})
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


def test_unscened_set_picker_projects_all_batches_grid(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """The All Batches picker must visibly project an unscened source grid."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {"text": 2, "upscale": 1},
    )

    harness.click_output_source_tab("alpha:text")
    harness.select_output_set(0)

    _assert_route(
        harness,
        alias="alpha",
        scene_key="",
        source_key="alpha:text",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:text"],
    )


def test_unscened_source_tabs_display_selected_output_at_every_batch_level(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Each source tab must display its own grid or concrete batch image."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {
            "output1": 3,
            "output2": 3,
            "output3": 3,
            "output4": 3,
            "output5": 3,
        },
    )
    source_keys = tuple(source_ids)

    harness.click_output_source_tab(source_keys[0])
    assert harness.output_set_picker_keys() == ("0", "1", "2", "3")
    for set_index in range(4):
        harness.select_output_set(set_index)
        for source_key in source_keys:
            harness.click_output_source_tab(source_key)
            expected_ids = source_ids[source_key]
            if set_index == 0:
                image_id = None
                visible_ids = expected_ids
            else:
                image_id = expected_ids[set_index - 1]
                visible_ids = (image_id,)
            _assert_route(
                harness,
                alias="alpha",
                scene_key="",
                source_key=source_key,
                set_index=set_index,
                image_id=image_id,
                visible_ids=visible_ids,
            )


def test_unscened_missing_batch_source_tab_cannot_claim_another_batch(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A CubeOutput without batch two must not select or display batch one."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {"text": 2, "upscale": 1},
    )
    harness.click_output_source_tab("alpha:text")
    harness.select_output_set(2)

    harness.click_output_source_tab("alpha:upscale")

    _assert_route(
        harness,
        alias="alpha",
        scene_key="",
        source_key="alpha:text",
        set_index=2,
        image_id=source_ids["alpha:text"][1],
        visible_ids=(source_ids["alpha:text"][1],),
    )


def test_unscened_missing_batch_picker_cannot_switch_cube_output(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A missing batch selection must not borrow another CubeOutput's image."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {"text": 2, "upscale": 1},
    )
    harness.click_output_source_tab("alpha:text")
    harness.select_output_set(1)
    harness.click_output_source_tab("alpha:upscale")

    harness.select_output_set(2)

    _assert_route(
        harness,
        alias="alpha",
        scene_key="",
        source_key="alpha:upscale",
        set_index=1,
        image_id=source_ids["alpha:upscale"][0],
        visible_ids=(source_ids["alpha:upscale"][0],),
    )


def test_single_scene_set_picker_projects_all_batches_grid(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """The All Batches picker must visibly project a one-scene source grid."""

    source_ids = _seed_single_scene_sources(
        harness,
        "alpha",
        {"text": 2, "upscale": 1},
    )

    harness.click_output_source_tab("alpha:text")
    harness.select_output_set(0)

    _assert_route(
        harness,
        alias="alpha",
        scene_key="scene1",
        source_key="alpha:text",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:text"],
    )


def test_batchless_scenes_hide_scene_and_batch_navigation(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Scenes with no batch alternatives should not expose hierarchy controls."""

    source_ids = _seed_sources(harness, "alpha", {"text": 1})

    overview = harness.fingerprint()
    assert overview.workflow_output_routes[harness.workflows["alpha"].workflow_id][1]
    assert overview.scene_selector_hidden, overview
    assert overview.set_selector_hidden, overview
    assert overview.navigation_container_hidden, overview

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
    assert scene.scene_selector_hidden, scene
    assert scene.set_selector_hidden, scene
    assert scene.navigation_container_hidden, scene
    assert set(scene.composition_image_ids) == set(source_ids["alpha:text"]), scene


def test_batched_scenes_show_only_available_hierarchy_controls(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Real scene batches should expose scene and batch navigation when relevant."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2})

    overview = harness.fingerprint()
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
    assert not scene.set_selector_hidden, scene
    assert not scene.navigation_container_hidden, scene
    assert set(scene.composition_image_ids) == set(source_ids["alpha:text"]), scene


def test_multi_image_source_tab_restores_grid_after_single_source_switch(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Returning to a batched source must restore its All Batches grid."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 1})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    harness.click_output_source_tab("alpha:upscale")

    harness.click_output_source_tab("alpha:text")

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:text",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:text"],
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


def test_source_grid_workflow_association_survives_switching(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Each workflow should restore only its own grid, tab, and durable route."""

    alpha_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:upscale", alpha_ids["alpha:upscale"])
    beta_ids = _seed_sources(harness, "beta", {"text": 2, "upscale": 2})
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
    harness.activate_workflow("beta")
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


def test_manual_source_grid_survives_new_output_arrival(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """New finals should not replace a manually selected source grid."""

    source_ids = _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    _enter_source_grid(harness, "alpha:text", source_ids["alpha:text"])
    run = harness.start_run("alpha", run_index=2)
    harness.emit_output(
        run,
        OutputSpec("alpha:other", "Other", (80, 90, 100)),
    )
    harness.wait_for_output_count("alpha", 13)

    _assert_route(
        harness,
        alias="alpha",
        source_key="alpha:text",
        set_index=0,
        image_id=None,
        visible_ids=source_ids["alpha:text"],
    )


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
        placement[1] for placement in harness.fingerprint().scene_layer_placements
    }
    assert len(alpha_overview_ids) == 3
    beta_ids = _seed_sources(harness, "beta", {"text": 2, "upscale": 1})
    _enter_source_grid(harness, "beta:text", beta_ids["beta:text"])

    harness.activate_workflow("alpha")

    fingerprint = harness.fingerprint()
    alpha_workflow_ids = set(fingerprint.workflow_output_image_ids[alpha_workflow_id])
    assert alpha_overview_ids <= alpha_workflow_ids
    assert set(fingerprint.composition_image_ids) == alpha_overview_ids, fingerprint
    assert fingerprint.workflow_output_routes[alpha_workflow_id][1] is True, fingerprint
    assert fingerprint.pane_current_image_id is None, fingerprint
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


def _seed_sources(
    harness: RealShellOutputCanvasHarness,
    alias: str,
    batch_counts: Mapping[str, int],
) -> dict[str, tuple[UUID, ...]]:
    """Create three workflow scenes with deterministic unequal source batches."""

    if alias not in harness.workflows:
        harness.add_workflow(alias, activate=True)
    else:
        harness.activate_workflow(alias)
    harness.show_canvas("Output")
    expected_count = 0
    for scene_index in range(3):
        run = harness.start_run(alias, run_index=scene_index + 1)
        scene = SceneSpec(
            run_id=f"scene-run-{alias}",
            key=f"scene{scene_index + 1}",
            title=f"scene{scene_index + 1}",
            order=scene_index,
            count=3,
        )
        for source_index, (source_name, batch_count) in enumerate(batch_counts.items()):
            source_key = f"{alias}:{source_name}"
            for batch_index in range(batch_count):
                harness.emit_output(
                    run,
                    OutputSpec(
                        source_key,
                        source_name.title(),
                        (
                            40 + source_index * 90,
                            40 + batch_index * 70,
                            180 - scene_index * 30,
                        ),
                        batch_index=batch_index,
                        scene=scene,
                    ),
                )
                expected_count += 1
        harness.wait_for_output_count(alias, expected_count)
        harness.complete_run(run)
    harness.project_workflow_directly(alias)
    return {
        f"{alias}:{source_name}": harness.output_ids_for_scene_source(
            scene_key="scene3",
            source_key=f"{alias}:{source_name}",
        )
        for source_name in batch_counts
    }


def _seed_unscened_sources(
    harness: RealShellOutputCanvasHarness,
    alias: str,
    batch_counts: Mapping[str, int],
) -> dict[str, tuple[UUID, ...]]:
    """Create deterministic unscened outputs for one workflow."""

    harness.add_workflow(alias, activate=True)
    harness.show_canvas("Output")
    run = harness.start_run(alias)
    expected_count = 0
    for source_index, (source_name, batch_count) in enumerate(batch_counts.items()):
        for batch_index in range(batch_count):
            harness.emit_output(
                run,
                OutputSpec(
                    f"{alias}:{source_name}",
                    source_name.title(),
                    (
                        40 + source_index * 90,
                        40 + batch_index * 70,
                        180 - source_index * 40,
                    ),
                    batch_index=batch_index,
                ),
            )
            expected_count += 1
    harness.wait_for_output_count(alias, expected_count)
    harness.complete_run(run)
    harness.project_workflow_directly(alias)
    projection = harness.shell.output_canvas._output_projection
    if projection is None:
        raise AssertionError("output projection is unavailable")
    return {
        source.source_key: tuple(
            item.image_id for _set_index, item in sorted(source.images_by_set.items())
        )
        for source in projection.sources
    }


def _seed_single_scene_sources(
    harness: RealShellOutputCanvasHarness,
    alias: str,
    batch_counts: Mapping[str, int],
) -> dict[str, tuple[UUID, ...]]:
    """Create deterministic outputs owned by one explicit scene."""

    harness.add_workflow(alias, activate=True)
    harness.show_canvas("Output")
    run = harness.start_run(alias)
    scene = SceneSpec(
        run_id=f"scene-run-{alias}",
        key="scene1",
        title="scene1",
        order=0,
        count=1,
    )
    expected_count = 0
    for source_index, (source_name, batch_count) in enumerate(batch_counts.items()):
        for batch_index in range(batch_count):
            harness.emit_output(
                run,
                OutputSpec(
                    f"{alias}:{source_name}",
                    source_name.title(),
                    (
                        40 + source_index * 90,
                        40 + batch_index * 70,
                        180 - source_index * 40,
                    ),
                    batch_index=batch_index,
                    scene=scene,
                ),
            )
            expected_count += 1
    harness.wait_for_output_count(alias, expected_count)
    harness.complete_run(run)
    harness.project_workflow_directly(alias)
    return {
        f"{alias}:{source_name}": harness.output_ids_for_scene_source(
            scene_key="scene1",
            source_key=f"{alias}:{source_name}",
        )
        for source_name in batch_counts
    }


def _enter_source_grid(
    harness: RealShellOutputCanvasHarness,
    source_key: str,
    expected_ids: tuple[UUID, ...],
) -> None:
    """Enter a scene grid through its rendered tile and source tabs."""

    alias = source_key.partition(":")[0]
    harness.click_canvas_image(harness.output_representative_id_for_scene("scene3"))
    harness.wait_until(
        lambda: (
            harness.fingerprint().workflow_output_routes[
                harness.workflows[alias].workflow_id
            ][:2]
            == ("scene3", False)
        )
    )
    if harness.fingerprint().active_source_tab_key != source_key:
        harness.click_output_source_tab(source_key)
    harness.wait_until(
        lambda: (
            {placement[1] for placement in harness.fingerprint().scene_layer_placements}
            == set(expected_ids)
        )
    )


def _assert_route(
    harness: RealShellOutputCanvasHarness,
    *,
    alias: str,
    scene_key: str = "scene3",
    source_key: str,
    set_index: int,
    image_id: UUID | None,
    visible_ids: tuple[UUID, ...],
) -> None:
    """Assert durable, rendered, tab, session, and workflow ownership agree."""

    fingerprint = harness.fingerprint()
    workflow_id = harness.workflows[alias].workflow_id
    route = fingerprint.workflow_output_routes[workflow_id]
    workflow_ids = set(fingerprint.workflow_output_image_ids[workflow_id])
    assert fingerprint.active_workflow_id == workflow_id, fingerprint
    assert fingerprint.output_session_workflow_id == workflow_id, fingerprint
    assert route == (scene_key, False, source_key, set_index, image_id), fingerprint
    assert fingerprint.active_source_tab_key == source_key, fingerprint
    assert set(fingerprint.composition_image_ids) <= workflow_ids, fingerprint
    assert fingerprint.pane_current_image_id is None or (
        fingerprint.pane_current_image_id in workflow_ids
    ), fingerprint
    if set_index == 0:
        assert fingerprint.pane_current_composition_id is not None, fingerprint
        assert set(fingerprint.composition_image_ids) == set(visible_ids), fingerprint
    else:
        assert fingerprint.pane_current_image_id == image_id, fingerprint
        if fingerprint.pane_current_composition_id is not None:
            assert set(fingerprint.composition_image_ids) == set(visible_ids), (
                fingerprint
            )
