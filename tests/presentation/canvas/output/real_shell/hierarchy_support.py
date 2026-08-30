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

"""Provide real-shell Output hierarchy fixture construction and route oracles."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness
from tests.support.real_output_canvas.models import OutputSpec, SceneSpec


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
            {placement[1] for placement in harness.fingerprint().grid_target_frames}
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
    assert set(fingerprint.presented_image_ids) <= workflow_ids, fingerprint
    assert fingerprint.active_image_id is None or (
        fingerprint.active_image_id in workflow_ids
    ), fingerprint
    if set_index == 0:
        assert fingerprint.active_composition_id is not None, fingerprint
        assert set(fingerprint.presented_image_ids) == set(visible_ids), fingerprint
    else:
        assert fingerprint.active_image_id == image_id, fingerprint
        if fingerprint.active_composition_id is not None:
            assert set(fingerprint.presented_image_ids) == set(visible_ids), fingerprint
