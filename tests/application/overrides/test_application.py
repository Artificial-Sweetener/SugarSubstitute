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

"""Verify overrides apply to editor projections and report writes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from substitute.application.node_behavior import OverridePinPolicy
from substitute.application.overrides import PinnedOverrideService
from substitute.application.workflows import (
    DIRECT_WORKFLOW_SECTION_KEY,
    WorkflowEditorProjectionService,
)
from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from tests.application.overrides.support import _field_spec, _snapshot


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
