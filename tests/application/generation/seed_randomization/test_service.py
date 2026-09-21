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
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    ResolvedFieldSpec,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.node_behavior import OverrideBehavior
from substitute.domain.node_behavior import FieldPresentation
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.application.workflows import DIRECT_WORKFLOW_SECTION_KEY
from substitute.domain.workflow import CubeState, WorkflowState


def _seed_value(workflow: WorkflowState, field_key: str = "seed") -> object:
    """Return the mutable test seed value from the workflow buffer."""

    buffer = workflow.cubes["Demo"].buffer
    nodes = cast(dict[str, object], buffer["nodes"])
    ksampler = cast(dict[str, object], nodes["KSampler"])
    inputs = cast(dict[str, object], ksampler["inputs"])
    return inputs[field_key]


def _workflow(*, seed_mode: SeedMode | None = None) -> WorkflowState:
    """Build a workflow with one KSampler seed field."""

    cube = CubeState(
        cube_id="owner/repo/demo.cube",
        version="1.0.0",
        alias="Demo",
        original_cube={"nodes": {}},
        buffer={"nodes": {"KSampler": {"inputs": {"seed": 7}}}},
    )
    if seed_mode is not None:
        cube.field_control_states = {"KSampler": {"seed": SeedControlState(seed_mode)}}
    return WorkflowState(cubes={"Demo": cube}, stack_order=["Demo"])


def _snapshot(
    *,
    minimum: int = 0,
    maximum: int = 999,
    field_key: str = "seed",
    cube_alias: str = "Demo",
) -> EditorBehaviorSnapshot:
    """Build a behavior snapshot with one seed field spec."""

    spec = ResolvedFieldSpec(
        cube_alias=cube_alias,
        node_name="KSampler",
        class_type="KSampler",
        field_key=field_key,
        field_type="INT",
        constraints={"min": minimum, "max": maximum},
        meta_info={},
        field_info=None,
        value=7,
        field_behavior=FieldBehavior(
            field_key=field_key,
            presentation=FieldPresentation.SEED_BOX,
            override_behavior=OverrideBehavior(
                override_key="seed" if field_key in {"seed", "noise_seed"} else None
            ),
        ),
    )
    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias={cube_alias: {"KSampler": {field_key: spec}}},
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def test_randomize_workflow_seeds_updates_random_editor_seed() -> None:
    """Random editor seed mode should write a new seed into the cube buffer."""

    workflow = _workflow()
    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=_snapshot(),
        randint=lambda lower, upper: lower + upper,
    )

    assert result.changed is True
    assert result.changes[0].value == 999
    assert _seed_value(workflow) == 999
    assert workflow.cubes["Demo"].dirty is True


def test_randomize_workflow_seeds_keeps_fixed_editor_seed() -> None:
    """Fixed editor seed mode should leave the cube buffer unchanged."""

    workflow = _workflow(seed_mode=SeedMode.FIXED)
    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=_snapshot(),
        randint=lambda _lower, _upper: 42,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7
    assert workflow.cubes["Demo"].dirty is False


def test_randomize_workflow_seeds_updates_random_override_seed() -> None:
    """Random override seed mode should update only the override value."""

    workflow = _workflow()
    workflow.global_overrides = {"seed": {"value": 10, "mode": "global"}}

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=_snapshot(minimum=5, maximum=20),
        randint=lambda lower, upper: lower * upper,
    )

    assert result.changed is True
    assert _seed_value(workflow) == 7
    assert workflow.global_overrides["seed"] == {"value": 100, "mode": "global"}


def test_randomize_workflow_seeds_keeps_fixed_override_seed() -> None:
    """Fixed override seed mode should leave override value and mode unchanged."""

    workflow = _workflow()
    workflow.global_overrides = {"seed": {"value": 10, "mode": "global"}}
    workflow.override_control_states = {"seed": SeedControlState(SeedMode.FIXED)}

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=_snapshot(),
        randint=lambda _lower, _upper: 99,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7
    assert workflow.global_overrides["seed"] == {"value": 10, "mode": "global"}


def test_randomize_workflow_seeds_skips_invalid_range() -> None:
    """Invalid seed bounds should skip randomization without mutating workflow state."""

    workflow = _workflow()

    result = SeedRandomizationService().randomize_workflow_seeds(
        workflow=workflow,
        behavior_snapshot=_snapshot(minimum=20, maximum=5),
        randint=lambda _lower, _upper: 99,
    )

    assert result.changed is False
    assert _seed_value(workflow) == 7


def test_randomize_workflow_seeds_updates_local_variation_seed() -> None:
    """Variation seeds should randomize as SeedBoxes without global participation."""

    workflow = _workflow()
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
        behavior_snapshot=_snapshot(field_key="variation_seed"),
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

    workflow = _workflow()
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
        behavior_snapshot=_snapshot(field_key="variation_seed"),
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
        behavior_snapshot=_snapshot(cube_alias=DIRECT_WORKFLOW_SECTION_KEY),
        randint=lambda _lower, _upper: 91,
    )

    assert result.changed is True
    assert direct.buffer["nodes"]["KSampler"]["inputs"]["seed"] == 91  # type: ignore[index]
    assert direct.source_workflow["nodes"]["KSampler"]["inputs"]["seed"] == 91  # type: ignore[index]
    assert direct.dirty is True
