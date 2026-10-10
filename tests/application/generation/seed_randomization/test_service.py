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

"""Tests for workflow-owned seed randomization."""

from __future__ import annotations

from typing import cast
from pathlib import Path

from substitute.application.generation.seed_randomization_service import (
    SeedRandomizationService,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.workflow import WorkflowState
from tests.application.generation.seed_randomization.seed_owner_fixtures import (
    seed_snapshot,
    seed_workflow,
)


def _seed_value(workflow: WorkflowState, field_key: str = "seed") -> object:
    """Return the mutable test seed value from the workflow buffer."""

    buffer = workflow.cubes["Demo"].buffer
    nodes = cast(dict[str, object], buffer["nodes"])
    ksampler = cast(dict[str, object], nodes["KSampler"])
    inputs = cast(dict[str, object], ksampler["inputs"])
    return inputs[field_key]


def test_randomize_workflow_seeds_updates_random_editor_seed() -> None:
    """Random editor seed mode should write a new seed into the cube buffer."""

    workflow = seed_workflow()
    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(),
        randint=lambda lower, upper: lower + upper,
    )

    assert result.changed is True
    assert result.changes[0].value == 999
    assert _seed_value(workflow) == 999
    assert workflow.cubes["Demo"].dirty is True


def test_randomize_workflow_seeds_keeps_fixed_editor_seed() -> None:
    """Fixed editor seed mode should leave the cube buffer unchanged."""

    workflow = seed_workflow(seed_mode=SeedMode.FIXED)
    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(),
        randint=lambda _lower, _upper: 42,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7
    assert workflow.cubes["Demo"].dirty is False


def test_randomize_workflow_seeds_updates_random_override_seed() -> None:
    """Random override seed mode should update only the override value."""

    workflow = seed_workflow()
    workflow.global_overrides = {"seed": {"value": 10, "mode": "global"}}

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(minimum=5, maximum=20),
        randint=lambda lower, upper: lower * upper,
    )

    assert result.changed is True
    assert _seed_value(workflow) == 7
    assert workflow.global_overrides["seed"] == {"value": 100, "mode": "global"}


def test_randomize_workflow_seeds_keeps_fixed_override_seed() -> None:
    """Fixed override seed mode should leave override value and mode unchanged."""

    workflow = seed_workflow()
    workflow.global_overrides = {"seed": {"value": 10, "mode": "global"}}
    workflow.override_control_states = {"seed": SeedControlState(SeedMode.FIXED)}

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(),
        randint=lambda _lower, _upper: 99,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7
    assert workflow.global_overrides["seed"] == {"value": 10, "mode": "global"}


def test_randomize_workflow_seeds_skips_invalid_range() -> None:
    """Invalid seed bounds should skip randomization without mutating workflow state."""

    workflow = seed_workflow()

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(minimum=20, maximum=5),
        randint=lambda _lower, _upper: 99,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7


def test_randomize_workflow_seeds_updates_local_variation_seed() -> None:
    """Variation seeds should randomize as SeedBoxes without global participation."""

    workflow = seed_workflow()
    inputs = cast(
        dict[str, object],
        cast(
            dict[str, object],
            cast(dict[str, object], workflow.cubes["Demo"].buffer["nodes"])["KSampler"],
        )["inputs"],
    )
    inputs["variation_seed"] = 13
    workflow.global_overrides = {"seed": {"value": 77, "mode": "global"}}
    random_values = iter((42, 99))

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(field_key="variation_seed"),
        randint=lambda _lower, _upper: next(random_values),
    )

    assert len(result.changes) == 2
    variation_change = result.changes[0]
    assert variation_change.field_key == "variation_seed"
    assert variation_change.override_key is None
    assert _seed_value(workflow, "variation_seed") == 42
    assert workflow.global_overrides["seed"]["value"] == 99


def test_randomize_workflow_seeds_keeps_locked_variation_seed() -> None:
    """A locked variation SeedBox should preserve its user-entered value."""

    workflow = seed_workflow()
    cube = workflow.cubes["Demo"]
    inputs = cast(
        dict[str, object],
        cast(
            dict[str, object],
            cast(dict[str, object], cube.buffer["nodes"])["KSampler"],
        )["inputs"],
    )
    inputs["variation_seed"] = 1234
    cube.field_control_states = {
        "KSampler": {"variation_seed": SeedControlState(SeedMode.FIXED)}
    }

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(field_key="variation_seed"),
        randint=lambda _lower, _upper: 42,
    )

    assert result.changed is False
    assert _seed_value(workflow, "variation_seed") == 1234


def test_randomize_workflow_seeds_updates_direct_workflow_canonical_value() -> None:
    """Direct workflow SeedBoxes should update editor and canonical graph storage."""

    direct = DirectWorkflowState(
        source_path=Path("demo.json"),
        source_workflow={
            "nodes": {"KSampler": {"inputs": {"seed": 7}}},
        },
        buffer={"nodes": {"KSampler": {"inputs": {"seed": 7}}}},
    )
    workflow = WorkflowState(direct_workflow=direct)

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=seed_snapshot(cube_alias=DIRECT_WORKFLOW_SECTION_KEY),
        randint=lambda _lower, _upper: 91,
    )

    assert result.changed is True
    assert direct.buffer["nodes"]["KSampler"]["inputs"]["seed"] == 91  # type: ignore[index]
    assert direct.source_workflow["nodes"]["KSampler"]["inputs"]["seed"] == 91  # type: ignore[index]
    assert direct.dirty is True
