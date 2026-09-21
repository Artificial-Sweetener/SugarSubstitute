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

"""Tests for queued seed capture and cross-workflow adoption."""

from __future__ import annotations

from typing import cast

from substitute.application.generation.seed_value_service import SeedValueService
from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    ResolvedFieldSpec,
)
from substitute.domain.generation import GenerationSeedValue
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.node_behavior import FieldPresentation, OverrideBehavior
from substitute.domain.workflow import CubeState, WorkflowState


def _workflow(
    aliases: tuple[str, ...],
    *,
    global_seed: int | None = None,
) -> WorkflowState:
    """Build a workflow with main and variation SeedBoxes for each alias."""

    cubes = {
        alias: CubeState(
            cube_id=f"owner/repo/{alias}.cube",
            version="1.0.0",
            alias=alias,
            original_cube={"nodes": {}},
            buffer={
                "nodes": {
                    "Sampler": {
                        "class_type": "KSampler",
                        "inputs": {
                            "seed": index + 10,
                            "variation_seed": index + 100,
                        },
                    }
                }
            },
        )
        for index, alias in enumerate(aliases)
    }
    workflow = WorkflowState(cubes=cubes, stack_order=list(aliases))
    if global_seed is not None:
        workflow.global_overrides = {"seed": {"value": global_seed, "mode": "global"}}
    return workflow


def _behavior(aliases: tuple[str, ...]) -> EditorBehaviorSnapshot:
    """Build main and variation SeedBox behavior for each workflow alias."""

    field_specs_by_alias: dict[str, dict[str, dict[str, ResolvedFieldSpec]]] = {}
    for alias in aliases:
        specs: dict[str, ResolvedFieldSpec] = {}
        for field_key in ("seed", "variation_seed"):
            specs[field_key] = ResolvedFieldSpec(
                cube_alias=alias,
                node_name="Sampler",
                class_type="KSampler",
                field_key=field_key,
                field_type="INT",
                constraints={"min": 0, "max": 9999},
                meta_info={},
                field_info=None,
                value=0,
                field_behavior=FieldBehavior(
                    field_key=field_key,
                    presentation=FieldPresentation.SEED_BOX,
                    override_behavior=OverrideBehavior(
                        override_key="seed" if field_key == "seed" else None
                    ),
                ),
            )
        field_specs_by_alias[alias] = {"Sampler": specs}
    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias=field_specs_by_alias,
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def _input(workflow: WorkflowState, alias: str, key: str) -> int:
    """Return one integer seed from the test workflow."""

    nodes = cast(dict[str, object], workflow.cubes[alias].buffer["nodes"])
    node = cast(dict[str, object], nodes["Sampler"])
    inputs = cast(dict[str, object], node["inputs"])
    return cast(int, inputs[key])


def test_capture_records_global_main_seed_and_local_variation_seed() -> None:
    """An active global override should replace local main seeds, not variations."""

    workflow = _workflow(("A", "B"), global_seed=777)

    values = SeedValueService().capture(
        workflow=workflow,
        behavior_snapshot=_behavior(("A", "B")),
    )

    assert values == (
        GenerationSeedValue(value=777, field_key="seed", override_key="seed"),
        GenerationSeedValue(
            value=100,
            field_key="variation_seed",
            cube_alias="A",
            node_name="Sampler",
            class_type="KSampler",
        ),
        GenerationSeedValue(
            value=101,
            field_key="variation_seed",
            cube_alias="B",
            node_name="Sampler",
            class_type="KSampler",
        ),
    )


def test_adopt_uses_current_global_override_and_preserves_variation_identity() -> None:
    """A current global override should take one main seed while variations stay local."""

    workflow = _workflow(("A", "B"), global_seed=1)
    workflow.override_control_states["seed"] = SeedControlState(SeedMode.FIXED)
    workflow.cubes["A"].field_control_states = {
        "Sampler": {"variation_seed": SeedControlState(SeedMode.FIXED)}
    }
    sources = (
        GenerationSeedValue(
            value=42,
            field_key="seed",
            cube_alias="Old A",
            node_name="Sampler",
            class_type="KSampler",
        ),
        GenerationSeedValue(
            value=501,
            field_key="variation_seed",
            cube_alias="A",
            node_name="Sampler",
            class_type="KSampler",
        ),
        GenerationSeedValue(
            value=502,
            field_key="variation_seed",
            cube_alias="B",
            node_name="Sampler",
            class_type="KSampler",
        ),
    )

    result = SeedValueService().adopt(
        workflow=workflow,
        behavior_snapshot=_behavior(("A", "B")),
        source_values=sources,
    )

    assert result.changed is True
    assert workflow.global_overrides["seed"]["value"] == 42
    assert _input(workflow, "A", "variation_seed") == 501
    assert _input(workflow, "B", "variation_seed") == 502
    assert workflow.override_control_states["seed"].mode is SeedMode.FIXED
    assert (
        workflow.cubes["A"].field_control_states["Sampler"]["variation_seed"].mode
        is SeedMode.FIXED
    )


def test_adopt_broadcasts_source_global_seed_to_local_main_seed_boxes() -> None:
    """One queued global seed should populate every effective current main seed."""

    workflow = _workflow(("A", "B", "C"))

    SeedValueService().adopt(
        workflow=workflow,
        behavior_snapshot=_behavior(("A", "B", "C")),
        source_values=(
            GenerationSeedValue(value=1234, field_key="seed", override_key="seed"),
        ),
    )

    assert [_input(workflow, alias, "seed") for alias in ("A", "B", "C")] == [
        1234,
        1234,
        1234,
    ]


def test_adopt_broadcasts_one_matching_local_seed_to_every_current_seed_box() -> None:
    """Identity matching must not prevent one-to-many mismatch recovery."""

    workflow = _workflow(("A", "B", "C"))

    SeedValueService().adopt(
        workflow=workflow,
        behavior_snapshot=_behavior(("A", "B", "C")),
        source_values=(
            GenerationSeedValue(
                value=4321,
                field_key="seed",
                cube_alias="A",
                node_name="Sampler",
                class_type="KSampler",
            ),
        ),
    )

    assert [_input(workflow, alias, "seed") for alias in ("A", "B", "C")] == [
        4321,
        4321,
        4321,
    ]


def test_adopt_pairs_mismatched_seed_counts_and_leaves_surplus_targets_armed() -> None:
    """Multiple unmatched sources should pair in order without inventing extra values."""

    workflow = _workflow(("A", "B", "C"))
    sources = (
        GenerationSeedValue(value=80, field_key="seed", cube_alias="X"),
        GenerationSeedValue(value=81, field_key="seed", cube_alias="Y"),
    )

    SeedValueService().adopt(
        workflow=workflow,
        behavior_snapshot=_behavior(("A", "B", "C")),
        source_values=sources,
    )

    assert [_input(workflow, alias, "seed") for alias in ("A", "B", "C")] == [
        80,
        81,
        12,
    ]
