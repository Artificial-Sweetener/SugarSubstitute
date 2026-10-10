"""Verify random global seeds fit every effective override participant."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from substitute.application.generation.seed_randomization_service import (
    DEFAULT_RANDOM_SEED_MAX,
    SeedRandomizationService,
)
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.application.workflows.editor_projection_service import (
    WorkflowEditorProjectionService,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.node_behavior import OverridePinPolicy
from substitute.domain.workflow import WorkflowState
from tests.application.generation.seed_randomization.seed_owner_fixtures import (
    seed_snapshot,
    seed_workflow,
)


def _bounded_workflow(
    fields: tuple[tuple[str, int, int], ...],
) -> tuple[WorkflowState, EditorBehaviorSnapshot]:
    """Build real seed owners with independently constrained override fields."""

    workflow = seed_workflow()
    workflow.global_overrides = {"seed": {"value": 7, "mode": "global"}}
    snapshot = seed_snapshot()
    specs: dict[str, dict[str, ResolvedFieldSpec]] = {}
    nodes: dict[str, object] = {}
    for index, (key, minimum, maximum) in enumerate(fields):
        node_name = f"Sampler{index}"
        spec = seed_snapshot(minimum=minimum, maximum=maximum, field_key=key)
        source = spec.field_specs_by_alias["Demo"]["KSampler"][key]
        specs[node_name] = {
            key: replace(
                source,
                node_name=node_name,
                field_behavior=replace(
                    source.field_behavior,
                    override_behavior=replace(
                        source.field_behavior.override_behavior,
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    ),
                ),
            )
        }
        nodes[node_name] = {"inputs": {key: 7}}
    workflow.cubes["Demo"].buffer["nodes"] = nodes
    return workflow, replace(snapshot, field_specs_by_alias={"Demo": specs})


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ((("noise_seed", 12, 999),), (12, 999)),
        ((("noise_seed", 12, 999), ("seed", 0, 2000)), (12, 999)),
        ((("seed", 0, 2000), ("noise_seed", 12, 999)), (12, 999)),
        ((("seed", 50, 2000), ("seed", 12, 999)), (50, 999)),
        ((("noise_seed", 999, 999),), (999, 999)),
        ((("noise_seed", 0, DEFAULT_RANDOM_SEED_MAX),), (0, DEFAULT_RANDOM_SEED_MAX)),
    ],
)
@pytest.mark.parametrize("choose_upper", [False, True])
def test_random_global_seed_fits_all_participating_inputs(
    fields: tuple[tuple[str, int, int], ...],
    expected: tuple[int, int],
    choose_upper: bool,
) -> None:
    """Aliases and mixed bounds must produce valid exact seeds at both endpoints."""

    workflow, snapshot = _bounded_workflow(fields)
    draws: list[tuple[int, int]] = []

    def draw(lower: int, upper: int) -> int:
        """Record the permitted range and choose a valid boundary value."""

        draws.append((lower, upper))
        return upper if choose_upper else lower

    SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow, behavior_snapshot=snapshot, randint=draw
    )
    assert draws == [expected]
    value = expected[1 if choose_upper else 0]
    assert workflow.global_overrides["seed"]["value"] == value
    projection = WorkflowEditorProjectionService().project(workflow)
    PinnedOverrideService().apply_overrides_to_projection(
        overrides=workflow.global_overrides,
        projection=projection,
        behavior_snapshot=snapshot,
    )
    nodes = cast(
        dict[str, dict[str, dict[str, int]]], workflow.cubes["Demo"].buffer["nodes"]
    )
    for index, (key, minimum, maximum) in enumerate(fields):
        assert nodes[f"Sampler{index}"]["inputs"][key] == value
        assert minimum <= value <= maximum


@pytest.mark.parametrize(
    "fields",
    [
        (("noise_seed", 20, 10),),
        (("seed", 0, 10), ("noise_seed", 20, 30)),
    ],
)
def test_invalid_shared_range_preserves_existing_seed(
    fields: tuple[tuple[str, int, int], ...],
) -> None:
    """Empty intersections retain the established skip-invalid-range policy."""

    workflow, snapshot = _bounded_workflow(fields)

    def draw(_lower: int, _upper: int) -> int:
        """Reject randomness when no shared valid seed exists."""

        pytest.fail("An invalid shared seed range must not draw a value")

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow, behavior_snapshot=snapshot, randint=draw
    )
    assert not result.changed
    assert workflow.global_overrides["seed"]["value"] == 7


@pytest.mark.parametrize("malformed_metadata", [False, True])
def test_fixed_global_seed_never_draws_or_clamps(malformed_metadata: bool) -> None:
    """Existing fixed values remain untouched even when metadata differs."""

    workflow, snapshot = _bounded_workflow((("noise_seed", 20, 30),))
    workflow.override_control_states["seed"] = SeedControlState(SeedMode.FIXED)
    if malformed_metadata:
        snapshot.field_specs_by_alias["Demo"]["Sampler0"]["noise_seed"].constraints[
            "max"
        ] = float("nan")

    def draw(_lower: int, _upper: int) -> int:
        """Reject random draws for a locked global seed."""

        pytest.fail("A fixed global seed must not draw a value")

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow, behavior_snapshot=snapshot, randint=draw
    )
    assert not result.changed
    assert workflow.global_overrides["seed"]["value"] == 7


def test_unmounted_snapshot_fields_do_not_constrain_global_seed() -> None:
    """Removed workflow sections cannot supply stale global random bounds."""

    workflow, snapshot = _bounded_workflow((("noise_seed", 12, 999),))
    stale = seed_snapshot(minimum=1, maximum=2, cube_alias="Removed")
    snapshot = replace(
        snapshot,
        field_specs_by_alias={
            **stale.field_specs_by_alias,
            **snapshot.field_specs_by_alias,
        },
    )
    draws: list[tuple[int, int]] = []

    def draw(lower: int, upper: int) -> int:
        """Record the active seed range."""

        draws.append((lower, upper))
        return upper

    SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow, behavior_snapshot=snapshot, randint=draw
    )
    assert draws == [(12, 999)]


@pytest.mark.parametrize("missing_snapshot", [False, True])
def test_unknown_global_bounds_preserve_uint64_fallback(missing_snapshot: bool) -> None:
    """Absent seed metadata keeps the existing full-width random seed range."""

    workflow, snapshot = _bounded_workflow((("noise_seed", 0, 999),))
    spec = snapshot.field_specs_by_alias["Demo"]["Sampler0"]["noise_seed"]
    snapshot = replace(
        snapshot,
        field_specs_by_alias={
            "Demo": {"Sampler0": {"noise_seed": replace(spec, constraints={})}}
        },
    )
    draws: list[tuple[int, int]] = []

    def draw(lower: int, upper: int) -> int:
        """Record exact fallback bounds and return their upper endpoint."""

        draws.append((lower, upper))
        return upper

    SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=None if missing_snapshot else snapshot,
        randint=draw,
    )
    assert draws == [(0, DEFAULT_RANDOM_SEED_MAX)]
    assert workflow.global_overrides["seed"]["value"] == DEFAULT_RANDOM_SEED_MAX


def test_nonparticipating_seed_does_not_constrain_override() -> None:
    """A seed forbidden from pinning cannot restrict participating seed aliases."""

    workflow, snapshot = _bounded_workflow((("seed", 1, 2), ("noise_seed", 12, 999)))
    source = snapshot.field_specs_by_alias["Demo"]["Sampler0"]["seed"]
    snapshot.field_specs_by_alias["Demo"]["Sampler0"]["seed"] = replace(
        source,
        field_behavior=replace(
            source.field_behavior,
            override_behavior=replace(
                source.field_behavior.override_behavior,
                pin_policy=OverridePinPolicy.NEVER,
            ),
        ),
    )
    draws: list[tuple[int, int]] = []

    def draw(lower: int, upper: int) -> int:
        """Record the range of eligible global participants."""

        draws.append((lower, upper))
        return upper

    SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow, behavior_snapshot=snapshot, randint=draw
    )
    assert draws == [(12, 999)]
