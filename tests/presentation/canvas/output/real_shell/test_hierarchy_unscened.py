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

"""Verify unscened Output hierarchy and source selection through real controls."""

from __future__ import annotations

from uuid import UUID

from tests.presentation.canvas.output.real_shell.hierarchy_support import (
    _assert_route,
    _enter_source_grid,
    _seed_single_scene_sources,
    _seed_sources,
    _seed_unscened_sources,
)
from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec


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


def test_unscened_single_image_cube_output_tabs_change_visible_document(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Each mouse-selected single-image Cube-output tab changes the document."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {"text": 1, "upscale": 1, "detail": 1},
    )
    expected_colors = {
        "alpha:text": (40, 40, 180),
        "alpha:upscale": (130, 40, 140),
        "alpha:detail": (220, 40, 100),
    }

    for source_key, expected_ids in source_ids.items():
        harness.select_output_source(source_key)
        _assert_route(
            harness,
            alias="alpha",
            scene_key="",
            source_key=source_key,
            set_index=1,
            image_id=expected_ids[0],
            visible_ids=expected_ids,
        )
        harness.assert_active_target_rendered(expected_colors[source_key])


def test_cube_output_tab_replaces_live_preview_with_selected_final(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """A mouse-selected Cube-output tab must replace an active live preview."""

    source_ids = _seed_unscened_sources(
        harness,
        "alpha",
        {"text": 1, "upscale": 1},
    )
    harness.click_output_source_tab("alpha:text")
    run = harness.start_run("alpha", run_index=10)
    harness.emit_preview(
        run,
        OutputSpec("alpha:text", "Text", (15, 215, 90)),
    )
    harness.wait_for_preview_count(1)
    harness.assert_preview_displayed(color=(15, 215, 90))

    harness.click_output_source_tab("alpha:upscale")

    _assert_route(
        harness,
        alias="alpha",
        scene_key="",
        source_key="alpha:upscale",
        set_index=1,
        image_id=source_ids["alpha:upscale"][0],
        visible_ids=source_ids["alpha:upscale"],
    )
    harness.assert_active_target_rendered((130, 40, 140))


def test_detail_inspection_groups_are_scoped_to_scene_and_batch(
    harness: RealShellOutputCanvasHarness,
) -> None:
    """Link Cube outputs only when both their scene and batch coordinates match."""

    _seed_sources(harness, "alpha", {"text": 2, "upscale": 2})
    expected_groups: set[frozenset[UUID]] = set()
    for scene_index in range(1, 4):
        scene_key = f"scene{scene_index}"
        text_ids = harness.output_ids_for_scene_source(
            scene_key=scene_key,
            source_key="alpha:text",
        )
        upscale_ids = harness.output_ids_for_scene_source(
            scene_key=scene_key,
            source_key="alpha:upscale",
        )
        for text_id, upscale_id in zip(text_ids, upscale_ids, strict=True):
            composition_ids = (
                harness.shell.output_canvas.document.composition_id_for(text_id),
                harness.shell.output_canvas.document.composition_id_for(upscale_id),
            )
            assert all(composition_id is not None for composition_id in composition_ids)
            expected_groups.add(frozenset(composition_ids))

    actual_groups = {
        frozenset(group.members)
        for group in harness.shell.output_canvas.workspace.session.inspection.groups()
    }

    assert actual_groups == expected_groups


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

    harness.select_output_source(source_keys[0])
    assert harness.output_set_picker_keys() == ("0", "1", "2", "3")
    for set_index in range(4):
        harness.select_output_set(set_index)
        for source_key in source_keys:
            harness.select_output_source(source_key)
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
