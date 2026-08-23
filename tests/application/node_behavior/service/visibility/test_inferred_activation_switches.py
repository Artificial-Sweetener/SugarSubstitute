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

"""Verify graph-aware activation-switch visibility."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    ActivationSwitchRole,
    ActivationSwitchSource,
    EnabledSwitchPolicy,
)
from tests.support.node_behavior import build_behavior_snapshot, cube_state

SEEDVR2_WRAPPER_ID = "9c18a058-dc20-4cde-a556-ad0d518710dc"


def _model_patch_definition() -> dict[str, object]:
    """Return a MODEL-transform definition."""

    return {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "gain": ["FLOAT", {"default": 0.0}],
            },
            "optional": {},
        },
        "output": ["MODEL"],
    }


def _model_input_non_model_output_definition() -> dict[str, object]:
    """Return a definition without a MODEL output."""

    return {
        "input": {"required": {"model": ["MODEL", {}]}, "optional": {}},
        "output": ["LATENT"],
    }


def _seedvr2_dit_loader_definition() -> dict[str, object]:
    """Return a SeedVR2 DiT loader definition."""

    return {
        "input": {"required": {}, "optional": {}},
        "output": ["SEEDVR2_DIT"],
    }


def _seedvr2_wrapper_subgraph() -> dict[str, object]:
    """Return a SeedVR2 wrapper subgraph."""

    return {
        "id": SEEDVR2_WRAPPER_ID,
        "name": "SeedVR2 Upscale by Factor",
        "inputs": [
            {"name": "image", "label": "Image", "type": "IMAGE", "linkIds": [1]},
            {"name": "dit", "label": "DiT", "type": "SEEDVR2_DIT", "linkIds": [2]},
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


def test_single_inferred_transform_hides_its_switch() -> None:
    """Suppress a switch for one required transform."""

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
        definitions_by_class={"MyModelPatch": _model_patch_definition()},
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["patch"]
    decision = snapshot.card_decisions_by_alias["A"]["patch"]
    assert behavior.card.activation_switch_role == ActivationSwitchRole.TYPED_TRANSFORM
    assert behavior.card.enabled_switch_source == ActivationSwitchSource.INFERRED
    assert decision.show_enabled_switch is False


def test_multiple_inferred_transforms_show_switches() -> None:
    """Show switches for independently selectable transforms."""

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
        definitions_by_class={"MyModelPatch": _model_patch_definition()},
    )

    assert snapshot.card_decisions_by_alias["A"]["patch_a"].show_enabled_switch is True
    assert snapshot.card_decisions_by_alias["A"]["patch_b"].show_enabled_switch is True


def test_seedvr2_wrapper_does_not_infer_an_activation_switch() -> None:
    """Keep a lone SeedVR2 wrapper always visible and enabled."""

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
            "SeedVR2LoadDiTModel": _seedvr2_dit_loader_definition(),
            "SeedVR2VideoUpscaler": _model_input_non_model_output_definition(),
        },
    )

    behavior = snapshot.resolved_nodes_by_alias["A"]["seedvr2_upscale_by_factor"]
    decision = snapshot.card_decisions_by_alias["A"]["seedvr2_upscale_by_factor"]
    assert behavior.card.activation_switch_role == ActivationSwitchRole.NONE
    assert behavior.card.enabled_switch_source == ActivationSwitchSource.DEFAULT
    assert decision.visible is True
    assert decision.enabled is True
    assert decision.show_enabled_switch is False


def test_host_authored_always_switch_bypasses_singleton_suppression() -> None:
    """Keep a host-authored always-switch visible for one node."""

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
