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

"""Enforce cross-layer Output navigation contracts in ordinary parallel CI."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_scene_navigation_selection import (
    OutputSceneNavigationSelection,
)
from substitute.domain.workflow import OutputFocusMode
from substitute.presentation.canvas.output.output_canvas_navigation_policy import (
    OutputCanvasNavigationPolicy,
)
from substitute.presentation.canvas.output.output_canvas_route_model import (
    OutputCanvasRouteModel,
)
from tests.support.output_canvas.navigation_contract import (
    OutputNavigationFixture,
    OutputSourceSpec,
    assert_output_navigation_contract,
    build_navigation_fixture,
)


@dataclass(frozen=True, slots=True)
class _ExpectedRoute:
    """Describe one canonical projection result without duplicating its algorithm."""

    kind: str
    scene_key: str | None
    source_key: str | None
    set_index: int


@pytest.mark.parametrize(
    ("fixture", "expected"),
    (
        (
            build_navigation_fixture(sources=()),
            _ExpectedRoute("empty", None, None, 1),
        ),
        (
            build_navigation_fixture(),
            _ExpectedRoute("output_image", "", "text", 1),
        ),
        (
            build_navigation_fixture(sources=(OutputSourceSpec("text", "Text", 3),)),
            _ExpectedRoute("source_grid", "", "text", 0),
        ),
        (
            build_navigation_fixture(
                sources=(
                    OutputSourceSpec("text", "Text", 1),
                    OutputSourceSpec("upscale", "Upscale", 1),
                )
            ),
            _ExpectedRoute("output_image", "", "upscale", 1),
        ),
        (
            build_navigation_fixture(scene_keys=("only",)),
            _ExpectedRoute("output_image", "only", "text", 1),
        ),
        (
            build_navigation_fixture(scene_keys=("day", "night")),
            _ExpectedRoute("scene_overview", "night", None, 1),
        ),
        (
            build_navigation_fixture(
                scene_keys=("day", "night"),
                sources=(OutputSourceSpec("text", "Text", 3),),
            ),
            _ExpectedRoute("scene_overview", "night", None, 1),
        ),
    ),
    ids=(
        "empty",
        "one-output",
        "unscened-batch-grid",
        "multiple-sources",
        "one-scene",
        "batchless-scenes",
        "batched-scenes",
    ),
)
def test_automatic_navigation_truth_matrix(
    fixture: OutputNavigationFixture,
    expected: _ExpectedRoute,
) -> None:
    """Automatic projection should satisfy every cross-layer route invariant."""

    contract = assert_output_navigation_contract(fixture)

    assert contract.route_identity.route_kind == expected.kind
    assert contract.projection.active_scene_key == expected.scene_key
    assert contract.projection.active_source_key == expected.source_key
    assert contract.projection.active_set_index == expected.set_index


@pytest.mark.parametrize(
    ("stale_scene", "stale_source", "stale_set"),
    (
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ),
)
def test_manual_stale_route_matrix_normalizes_to_valid_contract(
    stale_scene: bool,
    stale_source: bool,
    stale_set: bool,
) -> None:
    """Missing persisted coordinates should fall back without contradictions."""

    fixture = build_navigation_fixture(
        scene_keys=("day", "night"),
        sources=(
            OutputSourceSpec("text", "Text", 2),
            OutputSourceSpec("upscale", "Upscale", 1),
        ),
    )
    workflow = fixture.workflow
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_overview = False
    workflow.active_output_scene_key = "missing" if stale_scene else "day"
    workflow.active_output_source_key = "missing" if stale_source else "text"
    workflow.active_output_set_index = 99 if stale_set else 2
    workflow.active_output_uuid = None

    contract = assert_output_navigation_contract(fixture)

    assert contract.projection.active_scene_key in {"day", "night"}
    assert contract.projection.active_source_key in {"text", "upscale"}
    assert contract.projection.active_set_index in {1, 2}
    assert contract.projection.active_uuid in fixture.workflow.output_image_uuids


def test_manual_scene_grid_and_concrete_routes_share_cross_layer_identity() -> None:
    """Grid and concrete navigation should remain canonical across reprojection."""

    fixture = build_navigation_fixture(
        scene_keys=("day", "night"),
        sources=(OutputSourceSpec("text", "Text", 2),),
    )
    workflow = fixture.workflow
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_overview = False
    workflow.active_output_scene_key = "night"
    workflow.active_output_source_key = "text"
    workflow.active_output_set_index = 0
    workflow.active_output_uuid = None

    grid = assert_output_navigation_contract(fixture)

    assert grid.route_identity.route_kind == "source_grid"
    assert grid.projection.active_set_index == 0

    selected_id = fixture.image_id("night", "text", 2)
    workflow.active_output_set_index = 2
    workflow.active_output_uuid = selected_id

    concrete = assert_output_navigation_contract(fixture)

    assert concrete.route_identity.route_kind == "output_image"
    assert concrete.projection.active_uuid == selected_id

    workflow.active_output_set_index = 0
    workflow.active_output_uuid = None

    restored_grid = assert_output_navigation_contract(fixture)

    assert restored_grid.route_identity == grid.route_identity


def test_explicit_one_tile_grid_has_session_composition_authority() -> None:
    """A durable one-tile grid route should remain renderable after restore."""

    fixture = build_navigation_fixture()
    workflow = fixture.workflow
    workflow.output_focus_mode = OutputFocusMode.MANUAL
    workflow.active_output_scene_overview = False
    workflow.active_output_scene_key = ""
    workflow.active_output_source_key = "text"
    workflow.active_output_set_index = 0
    workflow.active_output_uuid = None

    contract = assert_output_navigation_contract(fixture)

    assert contract.route_identity.route_kind == "source_grid"
    assert contract.projection.set_count == 1


def test_numbered_direct_sources_keep_manifest_order_across_contract() -> None:
    """Direct source ordering should stay numeric through projection and session."""

    fixture = build_navigation_fixture(
        sources=(
            OutputSourceSpec("direct:blue:0", "2", 1),
            OutputSourceSpec("direct:red:0", "1", 1),
        )
    )

    contract = assert_output_navigation_contract(fixture)

    assert tuple(source.label for source in contract.projection.sources) == ("1", "2")


def test_scene_batch_source_drilldown_sequence_preserves_route_contract() -> None:
    """Every production state transition should project one authorized route."""

    fixture = build_navigation_fixture(
        scene_keys=("day", "night"),
        sources=(
            OutputSourceSpec("text", "Text", 2),
            OutputSourceSpec("upscale", "Upscale", 2),
        ),
    )
    registry = CanvasImageRegistry()
    for image_id, metadata in fixture.metadata_by_id.items():
        registry.store(image_id, payload=None, metadata=metadata)
    state = OutputCanvasStateService(image_registry=registry)

    overview = assert_output_navigation_contract(fixture)
    scenes = OutputCanvasRouteModel.scene_groups_by_key(
        overview.projection,
        preview_scene_groups_by_key={},
    )
    activation = OutputCanvasNavigationPolicy.scene_activation_plan(
        scene_key="night",
        scene_groups_by_key=scenes,
        was_scene_overview=True,
        active_source_key=None,
    )
    assert activation is not None
    assert activation.followup == "activate_grid"
    assert activation.active_source_key is not None
    state.set_active_output_scene(
        fixture.workflow,
        OutputSceneNavigationSelection(
            scene_key="night",
            overview=False,
            source_key=activation.active_source_key,
            set_index=0,
            image_id=None,
        ),
    )

    scene_grid = assert_output_navigation_contract(fixture)
    assert scene_grid.route_identity.route_kind == "source_grid"
    assert scene_grid.projection.active_scene_key == "night"

    selected_id = fixture.image_id("night", activation.active_source_key, 2)
    assert state.set_active_output_uuid(fixture.workflow, str(selected_id)) is not None

    concrete = assert_output_navigation_contract(fixture)
    assert concrete.projection.active_uuid == selected_id
    assert concrete.projection.active_set_index == 2

    state.set_active_output_grid(fixture.workflow, "upscale", "night")

    alternate_grid = assert_output_navigation_contract(fixture)
    assert alternate_grid.projection.active_source_key == "upscale"
    assert alternate_grid.projection.active_set_index == 0

    state.set_active_output_scene(
        fixture.workflow,
        OutputSceneNavigationSelection(
            scene_key=None,
            overview=True,
            source_key=None,
            set_index=1,
            image_id=None,
        ),
    )

    restored_overview = assert_output_navigation_contract(fixture)
    assert restored_overview.route_identity.route_kind == "scene_overview"


def test_workflow_switch_round_trip_preserves_each_route_identity() -> None:
    """A workflow switch should not leak or replace another workflow's route."""

    first = build_navigation_fixture(
        workflow_id="first",
        sources=(OutputSourceSpec("text", "Text", 2),),
    )
    first.workflow.output_focus_mode = OutputFocusMode.MANUAL
    first.workflow.active_output_source_key = "text"
    first.workflow.active_output_set_index = 0
    first_route = assert_output_navigation_contract(first).route_identity

    second = build_navigation_fixture(
        workflow_id="second",
        sources=(OutputSourceSpec("upscale", "Upscale", 1),),
    )
    second_id = second.image_id("", "upscale", 1)
    second.workflow.output_focus_mode = OutputFocusMode.MANUAL
    second.workflow.active_output_source_key = "upscale"
    second.workflow.active_output_set_index = 1
    second.workflow.active_output_uuid = second_id
    second_route = assert_output_navigation_contract(second).route_identity

    restored_first_route = assert_output_navigation_contract(first).route_identity

    assert first_route.route_kind == "source_grid"
    assert second_route.primary_image_id == second_id
    assert restored_first_route == first_route


def test_removed_active_output_normalizes_persisted_route_without_cross_workflow_ids() -> (
    None
):
    """Cache pruning should replace stale focus with a valid surviving route."""

    fixture = build_navigation_fixture(
        sources=(OutputSourceSpec("text", "Text", 3),),
    )
    removed_id = fixture.image_id("", "text", 3)
    fixture.workflow.output_focus_mode = OutputFocusMode.MANUAL
    fixture.workflow.active_output_source_key = "text"
    fixture.workflow.active_output_set_index = 3
    fixture.workflow.active_output_uuid = removed_id
    assert_output_navigation_contract(fixture)

    fixture.workflow.output_image_uuids.remove(removed_id)
    del fixture.metadata_by_id[removed_id]

    normalized = assert_output_navigation_contract(fixture)

    assert normalized.projection.active_uuid != removed_id
    assert normalized.projection.active_uuid in fixture.workflow.output_image_uuids
    assert normalized.projection.active_set_index in {1, 2}


def test_foreign_cached_uuid_falls_back_to_owned_output() -> None:
    """An old cache must not authorize an image outside workflow membership."""

    fixture = build_navigation_fixture()
    fixture.workflow.output_focus_mode = OutputFocusMode.MANUAL
    fixture.workflow.active_output_uuid = uuid4()
    fixture.workflow.active_output_source_key = "removed-source"
    fixture.workflow.active_output_set_index = 99

    normalized = assert_output_navigation_contract(fixture)

    assert normalized.projection.active_uuid in fixture.workflow.output_image_uuids
    assert normalized.projection.active_source_key == "text"
    assert normalized.projection.active_set_index == 1


def test_missing_cached_metadata_fails_to_an_empty_authorized_route() -> None:
    """An incomplete cache should not project membership without metadata."""

    fixture = build_navigation_fixture()
    fixture.metadata_by_id.clear()

    normalized = assert_output_navigation_contract(fixture)

    assert normalized.route_identity.route_kind == "empty"
    assert normalized.visible_image_ids == frozenset()
