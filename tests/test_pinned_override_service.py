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

"""Contract tests for the application pinned override service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.node_behavior import (
    EditorBehaviorSnapshot,
    FieldBehavior,
    OverrideBehavior,
    OverridePinPolicy,
    ResolvedFieldSpec,
)
from substitute.application.overrides import PinnedOverrideService
from substitute.application.workflows import (
    DIRECT_WORKFLOW_SECTION_KEY,
    WorkflowEditorProjectionService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState


def _field_spec(
    *,
    cube_alias: str,
    node_name: str,
    class_type: str,
    field_key: str,
    value: object,
    override_key: str | None,
    pin_policy: OverridePinPolicy,
    toolbar_order: int | None = None,
    toolbar_label: str | None = None,
    field_type: str = "STRING",
    field_info: list[object] | None = None,
) -> ResolvedFieldSpec:
    """Build one resolved field spec for focused pinned-override assertions."""

    return ResolvedFieldSpec(
        cube_alias=cube_alias,
        node_name=node_name,
        class_type=class_type,
        field_key=field_key,
        field_type=field_type,
        constraints={},
        meta_info={"cube_alias": cube_alias},
        field_info=field_info,
        value=value,
        field_behavior=FieldBehavior(
            field_key=field_key,
            override_behavior=OverrideBehavior(
                override_key=override_key,
                pin_policy=pin_policy,
                toolbar_label_override=toolbar_label,
                toolbar_order=toolbar_order,
            ),
        ),
    )


def _snapshot(
    field_specs_by_alias: dict[str, dict[str, dict[str, ResolvedFieldSpec]]],
) -> EditorBehaviorSnapshot:
    """Build the minimal behavior snapshot required by override service tests."""

    return EditorBehaviorSnapshot(
        resolved_nodes_by_alias={},
        field_specs_by_alias=field_specs_by_alias,
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
        reveal_entries_by_alias={},
    )


def test_participation_snapshot_uses_first_choice_field_as_authority() -> None:
    """Choice overrides should include exact and value-compatible participants only."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            },
            "B": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="B",
                        node_name="sampler",
                        class_type="CustomSampler",
                        field_key="sampler_name",
                        value="heun",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun", "dpmpp"], {"default": "euler"}],
                    )
                }
            },
            "C": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="C",
                        node_name="sampler",
                        class_type="TinySampler",
                        field_key="sampler_name",
                        value="ddim",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["ddim"], {"default": "ddim"}],
                    )
                }
            },
        }
    )

    participation = PinnedOverrideService().build_participation_snapshot(
        overrides={"sampler_name": {"value": "heun", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A", "B", "C"],
    )

    assert participation.participant_fields() == frozenset(
        {
            ("A", "sampler", "sampler_name"),
            ("B", "sampler", "sampler_name"),
        }
    )
    assert participation.eligible_fields_by_key["sampler_name"] == (
        ("A", "sampler", "sampler_name"),
        ("B", "sampler", "sampler_name"),
        ("C", "sampler", "sampler_name"),
    )


def test_serialization_scope_is_partial_when_not_all_choice_fields_participate() -> (
    None
):
    """Partial choice participation should serialize without a wildcard override."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            },
            "B": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="B",
                        node_name="sampler",
                        class_type="TinySampler",
                        field_key="sampler_name",
                        value="ddim",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["ddim"], {"default": "ddim"}],
                    )
                }
            },
        }
    )

    scope = PinnedOverrideService().build_serialization_scopes(
        overrides={"sampler_name": {"value": "heun", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
    )["sampler_name"]

    assert scope.full_participation is False
    assert scope.participant_fields == frozenset({("A", "sampler", "sampler_name")})


def test_choice_override_value_must_be_supported_by_authority() -> None:
    """Stale persisted choice values should not be applied to any participant."""

    snapshot = _snapshot(
        {
            "A": {
                "sampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="sampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=[["euler", "heun"], {"default": "euler"}],
                    )
                }
            }
        }
    )

    scope = PinnedOverrideService().build_serialization_scopes(
        overrides={"sampler_name": {"value": "ddim", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )["sampler_name"]

    assert scope.full_participation is False
    assert scope.participant_fields == frozenset()


def test_encode_style_scope_uses_wildcard_despite_hidden_same_key_link() -> None:
    """Hidden infrastructure inputs should not force encode style into partial scope."""

    encode_options: list[object] = [["A1111", "Comfy"], {"default": "A1111"}]
    snapshot = _snapshot(
        {
            "A": {
                "prompt_encode_style": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="prompt_encode_style",
                        class_type="SimpleSyrup.PromptEncodeStyle",
                        field_key="encode_style",
                        value="A1111",
                        override_key="encode_style",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
                "schedule_encode_prompts": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="schedule_encode_prompts",
                        class_type=(
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        field_key="encode_style",
                        value=["prompt_encode_style", 0],
                        override_key=None,
                        pin_policy=OverridePinPolicy.NEVER,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
            }
        }
    )
    service = PinnedOverrideService()

    participation = service.build_participation_snapshot(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )
    scope = service.build_serialization_scopes(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )["encode_style"]

    assert participation.participant_fields() == frozenset(
        {("A", "prompt_encode_style", "encode_style")}
    )
    assert participation.eligible_fields_by_key["encode_style"] == (
        ("A", "prompt_encode_style", "encode_style"),
    )
    assert scope.full_participation is True
    assert scope.participant_fields == frozenset(
        {("A", "prompt_encode_style", "encode_style")}
    )


def test_apply_overrides_to_projection_preserves_non_override_same_key_links() -> None:
    """Workflow writes should leave same-key non-participant graph links intact."""

    encode_options: list[object] = [["A1111", "Comfy"], {"default": "A1111"}]
    snapshot = _snapshot(
        {
            "A": {
                "prompt_encode_style": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="prompt_encode_style",
                        class_type="SimpleSyrup.PromptEncodeStyle",
                        field_key="encode_style",
                        value="A1111",
                        override_key="encode_style",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
                "schedule_encode_prompts": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="schedule_encode_prompts",
                        class_type=(
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        field_key="encode_style",
                        value=["prompt_encode_style", 0],
                        override_key=None,
                        pin_policy=OverridePinPolicy.NEVER,
                        field_type="LIST",
                        field_info=encode_options,
                    )
                },
            }
        }
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "prompt_encode_style": {"inputs": {"encode_style": "A1111"}},
                        "schedule_encode_prompts": {
                            "inputs": {"encode_style": ["prompt_encode_style", 0]}
                        },
                    }
                }
            )
        },
    )
    service = PinnedOverrideService()

    changed = service.apply_overrides_to_projection(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    nodes = workflow.cubes["A"].buffer["nodes"]
    assert changed is True
    assert nodes["prompt_encode_style"]["inputs"]["encode_style"] == "Comfy"
    assert nodes["schedule_encode_prompts"]["inputs"]["encode_style"] == [
        "prompt_encode_style",
        0,
    ]


def test_apply_overrides_updates_direct_workflow_editor_graph() -> None:
    """The shared override writer should mutate a direct graph projection."""

    snapshot = _snapshot(
        {
            DIRECT_WORKFLOW_SECTION_KEY: {
                "13": {
                    "noise_seed": _field_spec(
                        cube_alias=DIRECT_WORKFLOW_SECTION_KEY,
                        node_name="13",
                        class_type="KSamplerAdvanced",
                        field_key="noise_seed",
                        value=7,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    )
                }
            }
        }
    )
    workflow = WorkflowState(
        direct_workflow=DirectWorkflowState(
            source_path=Path("direct.json"),
            source_workflow={"nodes": []},
            buffer={
                "nodes": {
                    "13": {
                        "class_type": "KSamplerAdvanced",
                        "inputs": {"noise_seed": 7},
                    }
                }
            },
        )
    )

    changed = PinnedOverrideService().apply_overrides_to_projection(
        overrides={"seed": {"value": 42, "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    assert changed is True
    direct_workflow = workflow.direct_workflow
    assert direct_workflow is not None
    nodes = direct_workflow.buffer["nodes"]
    assert isinstance(nodes, dict)
    sampler = nodes["13"]
    assert isinstance(sampler, dict)
    inputs = sampler["inputs"]
    assert isinstance(inputs, dict)
    assert inputs["noise_seed"] == 42


def test_build_toolbar_snapshot_orders_candidates_deterministically() -> None:
    """Candidates should group by override key and sort by toolbar order then label."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                    "scheduler": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="scheduler",
                        value="karras",
                        override_key="scheduler",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=30,
                    ),
                }
            },
            "B": {
                "seed_node": {
                    "seed": _field_spec(
                        cube_alias="B",
                        node_name="seed_node",
                        class_type="SeedNode",
                        field_key="seed",
                        value=123,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    ),
                    "cfg": _field_spec(
                        cube_alias="B",
                        node_name="seed_node",
                        class_type="SeedNode",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=40,
                        toolbar_label="Guidance",
                    ),
                }
            },
        }
    )
    service = PinnedOverrideService()

    toolbar_snapshot = service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
        overrides={"sampler_name": {"value": "euler", "mode": "global"}},
    )

    assert [candidate.override_key for candidate in toolbar_snapshot.candidates] == [
        "seed",
        "sampler_name",
        "scheduler",
        "cfg",
    ]
    assert [candidate.label for candidate in toolbar_snapshot.candidates] == [
        "seed",
        "sampler_name",
        "scheduler",
        "Guidance",
    ]
    assert [control.override_key for control in toolbar_snapshot.active_controls] == [
        "sampler_name"
    ]


def test_build_toolbar_snapshot_skips_choice_candidates_without_options() -> None:
    """Toolbar choices should not treat unresolved fallback values as inventories."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                        field_type="LIST",
                        field_info=["LIST", {"dynamic": True}],
                    ),
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=123,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                }
            }
        }
    )

    toolbar_snapshot = PinnedOverrideService().build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides={},
    )

    assert [candidate.override_key for candidate in toolbar_snapshot.candidates] == [
        "seed"
    ]


def test_materialize_default_overrides_uses_first_representative_values() -> None:
    """Default-pinned controls should materialize from the first stack representative."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            },
            "B": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="B",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=222,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            },
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A", "B"],
    )

    assert changed is True
    assert overrides == {"seed": {"value": 111, "mode": "global"}}


def test_default_pinned_false_selection_prevents_materialization() -> None:
    """Explicitly unchecked default-pinned controls should stay inactive."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    )
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        selections={"seed": False},
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )

    assert changed is False
    assert overrides == {}


def test_normalize_workflow_selections_canonicalizes_legacy_sampler_key() -> None:
    """Persisted selection keys should normalize through the same canonical map."""

    service = PinnedOverrideService()

    normalized = service.normalize_workflow_selections(
        {"sampler": False, "cfg": True, "bad": "yes"}
    )

    assert normalized == {"sampler_name": False, "cfg": True}


def test_materialize_default_overrides_skips_optional_steps_and_cfg() -> None:
    """Optional sampler controls should remain inactive during default materialization."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "seed": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="seed",
                        value=111,
                        override_key="seed",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=10,
                    ),
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=20,
                    ),
                    "scheduler": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="scheduler",
                        value="karras",
                        override_key="scheduler",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                        toolbar_order=30,
                    ),
                    "steps": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="steps",
                        value=20,
                        override_key="steps",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=40,
                    ),
                    "cfg": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=50,
                    ),
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.materialize_default_overrides(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A"],
    )

    assert changed is True
    assert overrides == {
        "seed": {"value": 111, "mode": "global"},
        "sampler_name": {"value": "euler", "mode": "global"},
        "scheduler": {"value": "karras", "mode": "global"},
    }


def test_pin_override_activates_optional_cfg_candidate() -> None:
    """Optional candidates should activate explicitly without special-case handling."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "cfg": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="cfg",
                        value=7.0,
                        override_key="cfg",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                        toolbar_order=50,
                    )
                }
            }
        }
    )
    service = PinnedOverrideService()
    overrides: dict[str, dict[str, object]] = {}

    changed = service.pin_override(
        overrides=overrides,
        behavior_snapshot=snapshot,
        stack_order=["A"],
        override_key="cfg",
    )

    assert changed is True
    assert overrides == {"cfg": {"value": 7.0, "mode": "global"}}


def test_apply_overrides_to_projection_uses_override_key_mapping() -> None:
    """Workflow application should follow override keys rather than raw field names."""

    snapshot = _snapshot(
        {
            "A": {
                "style_a": {
                    "strength": _field_spec(
                        cube_alias="A",
                        node_name="style_a",
                        class_type="StyleNode",
                        field_key="strength",
                        value=0.2,
                        override_key="style_strength",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                    )
                },
                "style_b": {
                    "amount": _field_spec(
                        cube_alias="A",
                        node_name="style_b",
                        class_type="StyleNode",
                        field_key="amount",
                        value=0.4,
                        override_key="style_strength",
                        pin_policy=OverridePinPolicy.OPTIONAL,
                    )
                },
            }
        }
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "style_a": {"inputs": {"strength": 0.2}},
                        "style_b": {"inputs": {"amount": 0.4}},
                    }
                }
            )
        },
    )
    service = PinnedOverrideService()

    changed = service.apply_overrides_to_projection(
        overrides={"style_strength": {"value": 0.75, "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    assert changed is True
    assert workflow.cubes["A"].buffer["nodes"]["style_a"]["inputs"]["strength"] == 0.75
    assert workflow.cubes["A"].buffer["nodes"]["style_b"]["inputs"]["amount"] == 0.75


def test_apply_overrides_to_projection_reports_changed_sampler_write() -> None:
    """Changed override writes should force callers to rebuild stale snapshots."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    )
                }
            }
        }
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": ""}}}}
            )
        },
    )
    service = PinnedOverrideService()

    changed = service.apply_overrides_to_projection(
        overrides={"sampler_name": {"value": "euler_ancestral", "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    assert changed is True
    assert (
        workflow.cubes["A"].buffer["nodes"]["ksampler"]["inputs"]["sampler_name"]
        == "euler_ancestral"
    )


def test_apply_overrides_to_projection_reports_unchanged_equal_values() -> None:
    """Equal override writes should allow callers to reuse current snapshots."""

    snapshot = _snapshot(
        {
            "A": {
                "ksampler": {
                    "sampler_name": _field_spec(
                        cube_alias="A",
                        node_name="ksampler",
                        class_type="KSampler",
                        field_key="sampler_name",
                        value="euler_ancestral",
                        override_key="sampler_name",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    )
                }
            }
        }
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "ksampler": {
                            "inputs": {"sampler_name": "euler_ancestral"},
                        }
                    }
                }
            )
        },
    )
    service = PinnedOverrideService()

    changed = service.apply_overrides_to_projection(
        overrides={"sampler_name": {"value": "euler_ancestral", "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    assert changed is False
    assert (
        workflow.cubes["A"].buffer["nodes"]["ksampler"]["inputs"]["sampler_name"]
        == "euler_ancestral"
    )


def test_apply_overrides_to_projection_materializes_snapshot_backed_inputs() -> None:
    """Snapshot-backed overrides should write definition-backed missing inputs."""

    snapshot = _snapshot(
        {
            "A": {
                "prompt_encode_style": {
                    "encode_style": _field_spec(
                        cube_alias="A",
                        node_name="prompt_encode_style",
                        class_type="SimpleSyrup.PromptEncodeStyle",
                        field_key="encode_style",
                        value="A1111",
                        override_key="encode_style",
                        pin_policy=OverridePinPolicy.DEFAULT_PINNED,
                    )
                }
            }
        }
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {
                        "prompt_encode_style": {
                            "class_type": "SimpleSyrup.PromptEncodeStyle",
                            "inputs": {},
                        }
                    }
                }
            )
        },
    )
    service = PinnedOverrideService()

    changed = service.apply_overrides_to_projection(
        overrides={"encode_style": {"value": "Comfy", "mode": "global"}},
        projection=WorkflowEditorProjectionService().project(workflow),
        behavior_snapshot=snapshot,
    )

    assert changed is True
    inputs = workflow.cubes["A"].buffer["nodes"]["prompt_encode_style"]["inputs"]
    assert inputs["encode_style"] == "Comfy"


def test_normalize_workflow_overrides_canonicalizes_legacy_sampler_key() -> None:
    """Persisted legacy sampler keys should normalize to sampler_name."""

    service = PinnedOverrideService()

    normalized = service.normalize_workflow_overrides(
        {"sampler": {"value": "euler", "mode": "global"}}
    )

    assert normalized == {"sampler_name": {"value": "euler", "mode": "global"}}
