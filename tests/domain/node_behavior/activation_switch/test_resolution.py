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

"""Verify resolved activation-switch policy."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.node_behavior import (
    ActivationSwitchRole,
    ActivationSwitchSource,
    EnabledSwitchPolicy,
    NodeBehaviorContext,
    resolve_node_behavior,
)

NodeDefinition = dict[str, object]


def _model_patch_definition() -> NodeDefinition:
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


def _model_input_non_model_output_definition() -> NodeDefinition:
    """Return a definition without a MODEL output."""

    return {
        "input": {"required": {"model": ["MODEL", {}]}, "optional": {}},
        "output": ["LATENT"],
    }


def _sampler_worker_definition() -> NodeDefinition:
    """Return a sampler-worker-shaped definition."""

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


def _sampler_subgraph_wrapper_definition() -> NodeDefinition:
    """Return a sampler-worker wrapper definition."""

    return {
        **_sampler_worker_definition(),
        "subgraph_wrapper": True,
    }


def _non_sampler_subgraph_wrapper_definition() -> NodeDefinition:
    """Return a non-sampler wrapper definition."""

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


def _context(
    node_definition: Mapping[str, object] | None,
    *,
    class_type: str = "MyModelPatch",
) -> NodeBehaviorContext:
    """Build one direct node-behavior resolution context."""

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


def test_resolver_uses_model_patch_heuristic_without_overrides() -> None:
    """Resolve model-patch behavior from the live definition."""

    resolved = resolve_node_behavior(
        node_name="my_patch",
        class_type="MyModelPatch",
        input_keys=("model", "gain"),
        context=_context(_model_patch_definition()),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.INFERRED
    assert resolved.card.activation_switch_role == ActivationSwitchRole.TYPED_TRANSFORM
    assert resolved.card.activation_signal_types == frozenset({"MODEL"})


def test_resolver_marks_sampler_worker_as_never_switch() -> None:
    """Resolve sampler workers to the application icon and no switch."""

    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="CustomSamplerWorker",
        input_keys=("model", "steps", "denoise"),
        context=_context(
            _sampler_worker_definition(), class_type="CustomSamplerWorker"
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.icon_name == "application"


def test_resolver_prioritizes_sampler_worker_over_subgraph_wrapper() -> None:
    """Keep sampler-worker policy ahead of generic wrapper policy."""

    resolved = resolve_node_behavior(
        node_name="detailer",
        class_type="SubgraphWrapper",
        input_keys=("model", "steps", "denoise"),
        context=_context(
            _sampler_subgraph_wrapper_definition(),
            class_type="SubgraphWrapper",
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.icon_name == "application"


def test_resolver_keeps_non_sampler_subgraph_wrapper_switch() -> None:
    """Keep the generic wrapper switch for non-sampler wrappers."""

    resolved = resolve_node_behavior(
        node_name="patch_wrapper",
        class_type="SubgraphWrapper",
        input_keys=("model", "strength"),
        context=_context(
            _non_sampler_subgraph_wrapper_definition(),
            class_type="SubgraphWrapper",
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS


def test_resolver_keeps_host_ksampler_policy() -> None:
    """Keep the host-authored KSampler policy above inference."""

    resolved = resolve_node_behavior(
        node_name="sampler",
        class_type="KSampler",
        input_keys=("model",),
        context=_context(
            _model_input_non_model_output_definition(),
            class_type="KSampler",
        ),
    )

    assert resolved.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert resolved.card.enabled_switch_source == ActivationSwitchSource.HOST
