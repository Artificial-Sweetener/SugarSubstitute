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

"""Contract tests for model-patch enabled-switch inference."""

from __future__ import annotations

from substitute.application.node_behavior import (
    ActivationSwitchRole,
    ActivationSwitchSource,
    EnabledSwitchPolicy,
    NodeBehaviorContext,
    infer_model_patch_switch,
    infer_sampler_worker_node,
    resolve_node_behavior,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


SEEDVR2_WRAPPER_ID = "9c18a058-dc20-4cde-a556-ad0d518710dc"


def _model_patch_def():
    return {
        "input": {
            "required": {
                "model": ["MODEL", {"tooltip": "model input"}],
                "gain": ["FLOAT", {"default": 0.0}],
            },
            "optional": {},
        },
        "output": ["MODEL"],
    }


def _model_output_only_def():
    return {
        "input": {
            "required": {
                "ckpt_name": [
                    ["a.safetensors", "b.safetensors"],
                    {"default": "a.safetensors"},
                ],
            },
            "optional": {},
        },
        "output": ["MODEL", "CLIP", "VAE"],
    }


def _model_input_non_model_output_def():
    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
            },
            "optional": {},
        },
        "output": ["LATENT"],
    }


def _seedvr2_dit_loader_def():
    """Return a resource source definition matching the SeedVR2 DiT loader."""

    return {
        "input": {"required": {}, "optional": {}},
        "output": ["SEEDVR2_DIT"],
    }


def _seedvr2_wrapper_subgraph():
    """Return a SeedVR2-shaped wrapper that consumes DiT and outputs images."""

    return {
        "id": SEEDVR2_WRAPPER_ID,
        "name": "SeedVR2 Upscale by Factor",
        "inputs": [
            {"name": "image", "label": "Image", "type": "IMAGE", "linkIds": [1]},
            {
                "name": "dit",
                "label": "DiT",
                "type": "SEEDVR2_DIT",
                "linkIds": [2],
            },
        ],
        "outputs": [{"name": "IMAGE", "label": "Image", "type": "IMAGE"}],
        "links": [
            {"id": 1, "origin_id": -10, "target_id": 10, "target_slot": 0},
            {"id": 2, "origin_id": -10, "target_id": 10, "target_slot": 1},
        ],
        "nodes": [
            {
                "id": 10,
                "type": "SeedVR2VideoUpscaler",
                "inputs": [
                    {"name": "image", "type": "IMAGE"},
                    {"name": "dit", "type": "SEEDVR2_DIT"},
                ],
            }
        ],
    }


def _sampler_worker_def():
    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "steps": ["INT", {"default": 20}],
                "denoise": ["FLOAT", {"default": 1.0}],
            },
            "optional": {},
        },
        "output": ["LATENT"],
    }


def _sampler_subgraph_wrapper_def():
    definition = _sampler_worker_def()
    definition["subgraph_wrapper"] = True
    return definition


def _non_sampler_subgraph_wrapper_def():
    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "strength": ["FLOAT", {"default": 1.0}],
            },
            "optional": {},
        },
        "output": ["MODEL"],
        "subgraph_wrapper": True,
    }


def _context(node_definition, *, class_type: str = "MyModelPatch"):
    return NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name="patch",
        class_type=class_type,
        node_title=None,
        live_node_definition=node_definition,
        declarative_patch=None,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
    )


def test_infer_enabled_switch_true_for_model_patch():
    assert infer_model_patch_switch(_model_patch_def()) is True


def test_infer_enabled_switch_false_without_model_input():
    assert infer_model_patch_switch(_model_output_only_def()) is False


def test_infer_enabled_switch_false_without_model_output():
    assert infer_model_patch_switch(_model_input_non_model_output_def()) is False


def test_infer_enabled_switch_false_on_invalid():
    assert infer_model_patch_switch(None) is False
    assert infer_model_patch_switch({}) is False


def test_infer_sampler_worker_true_for_steps_and_denoise_definition():
    assert (
        infer_sampler_worker_node(
            _sampler_worker_def(),
            input_keys=("model", "steps", "denoise"),
        )
        is True
    )


def test_infer_sampler_worker_true_from_input_keys_fallback():
    assert infer_sampler_worker_node(None, input_keys=("steps", "denoise")) is True


def test_infer_sampler_worker_false_when_required_input_missing():
    assert infer_sampler_worker_node(None, input_keys=("steps",)) is False


def test_infer_sampler_worker_false_for_non_numeric_definition():
    definition = _sampler_worker_def()
    definition["input"]["required"]["denoise"] = ["STRING", {"default": "1.0"}]

    assert (
        infer_sampler_worker_node(
            definition,
            input_keys=("model", "steps", "denoise"),
        )
        is False
    )


def test_resolver_uses_heuristic_when_no_overrides_or_host_defaults():
    resolved = resolve_node_behavior(
        node_name="my_patch",
        class_type="MyModelPatch",
        input_keys=("model", "gain"),
        context=_context(_model_patch_def()),
    )
    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.INFERRED
    assert resolved.card.activation_switch_role == ActivationSwitchRole.TYPED_TRANSFORM
    assert resolved.card.activation_signal_types == frozenset({"MODEL"})


def test_single_normal_typed_transform_suppresses_inferred_switch() -> None:
    """A lone inferred transform is required in context and should not show a switch."""

    cube = cube_state(
        nodes={
            "patch": {
                "class_type": "MyModelPatch",
                "inputs": {"model": ["loader", 0], "gain": 0.25},
            }
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={"MyModelPatch": _model_patch_def()},
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["patch"]
    decision = snapshot.card_decisions_by_alias["A"]["patch"]
    assert behavior.card.activation_switch_role == ActivationSwitchRole.TYPED_TRANSFORM
    assert behavior.card.enabled_switch_source == ActivationSwitchSource.INFERRED
    assert decision.show_enabled_switch is False


def test_multiple_normal_typed_transforms_show_inferred_switches() -> None:
    """Multiple inferred transforms in one signal group should be switchable."""

    cube = cube_state(
        nodes={
            "patch_a": {
                "class_type": "MyModelPatch",
                "inputs": {"model": ["loader", 0], "gain": 0.25},
            },
            "patch_b": {
                "class_type": "MyModelPatch",
                "inputs": {"model": ["patch_a", 0], "gain": 0.5},
            },
        },
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={"MyModelPatch": _model_patch_def()},
    )

    assert snapshot.card_decisions_by_alias["A"]["patch_a"].show_enabled_switch is True
    assert snapshot.card_decisions_by_alias["A"]["patch_b"].show_enabled_switch is True


def test_seedvr2_style_wrapper_does_not_get_switch_from_subgraph_identity() -> None:
    """A lone SeedVR2-shaped wrapper should not be switchable because it is a wrapper."""

    cube = cube_state(
        nodes={
            "seedvr2_down_load_dit_model": {
                "class_type": "SeedVR2LoadDiTModel",
                "inputs": {},
            },
            "seedvr2_upscale_by_factor": {
                "class_type": SEEDVR2_WRAPPER_ID,
                "inputs": {
                    "image": ["@binding", "input.value"],
                    "dit": ["seedvr2_down_load_dit_model", 0],
                },
            },
        },
        subgraphs=[_seedvr2_wrapper_subgraph()],
    )

    snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "SeedVR2LoadDiTModel": _seedvr2_dit_loader_def(),
            "SeedVR2VideoUpscaler": _model_input_non_model_output_def(),
        },
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["seedvr2_upscale_by_factor"]
    decision = snapshot.card_decisions_by_alias["A"]["seedvr2_upscale_by_factor"]
    assert behavior.card.activation_switch_role == ActivationSwitchRole.NONE
    assert behavior.card.enabled_switch_source == ActivationSwitchSource.DEFAULT
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.show_enabled_switch is False


def test_resolver_marks_sampler_worker_as_never_switch_with_application_icon():
    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="CustomSamplerWorker",
        input_keys=("model", "steps", "denoise"),
        context=_context(_sampler_worker_def(), class_type="CustomSamplerWorker"),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.icon_name == "application"


def test_resolver_sampler_worker_wins_over_subgraph_wrapper_switch():
    resolved = resolve_node_behavior(
        node_name="detailer",
        class_type="SubgraphWrapper",
        input_keys=("model", "steps", "denoise"),
        context=_context(
            _sampler_subgraph_wrapper_def(),
            class_type="SubgraphWrapper",
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.icon_name == "application"


def test_resolver_keeps_subgraph_wrapper_switch_for_non_sampler_wrapper():
    resolved = resolve_node_behavior(
        node_name="patch_wrapper",
        class_type="SubgraphWrapper",
        input_keys=("model", "strength"),
        context=_context(
            _non_sampler_subgraph_wrapper_def(),
            class_type="SubgraphWrapper",
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS


def test_resolver_ksampler_is_explicitly_never_switch():
    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="KSampler",
        input_keys=("model",),
        context=_context(_model_input_non_model_output_def(), class_type="KSampler"),
    )
    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.HOST


def test_host_authored_always_switch_remains_intentional_for_single_node() -> None:
    """Host-authored ALWAYS policy should bypass inferred singleton suppression."""

    cube = cube_state(
        nodes={
            "vectorscope": {
                "class_type": "VectorscopeCC",
                "inputs": {"brightness": 0.5, "contrast": 0.25},
            }
        }
    )

    snapshot = build_behavior_snapshot(cube_states={"A": cube}, stack_order=["A"])

    behavior = snapshot.resolved_nodes_by_alias["A"]["vectorscope"]
    decision = snapshot.card_decisions_by_alias["A"]["vectorscope"]
    assert behavior.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert behavior.card.enabled_switch_source == ActivationSwitchSource.HOST
    assert decision.show_enabled_switch is True
