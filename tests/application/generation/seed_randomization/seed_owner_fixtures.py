"""Build seed-owner workflow and metadata fixtures for randomization contracts."""

from __future__ import annotations

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    ResolvedFieldSpec,
)
from substitute.domain.generation.seed_control import SeedControlState, SeedMode
from substitute.domain.node_behavior import (
    FieldPresentation,
    OverrideBehavior,
    OverridePinPolicy,
)
from substitute.domain.workflow import CubeState, WorkflowState


def seed_workflow(*, seed_mode: SeedMode | None = None) -> WorkflowState:
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


def seed_snapshot(
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
                override_key="seed" if field_key in {"seed", "noise_seed"} else None,
                pin_policy=OverridePinPolicy.DEFAULT_PINNED,
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
