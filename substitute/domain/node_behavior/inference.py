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

"""Infer default node behavior from live node definitions when host defaults are absent."""

from __future__ import annotations

import re
from typing import Final
from typing import Mapping

from .models import (
    ActivationSwitchRole,
    ActivationSwitchSource,
    CardBehaviorPatch,
    EnabledSwitchPolicy,
    NodeBehaviorPatch,
    PromptRole,
)

_SAMPLER_WORKER_INPUTS = frozenset({"steps", "denoise"})
_INTEGER_LIKE_INPUT_TYPES = frozenset({"INT", "INTEGER", "FLOAT", "NUMBER"})
_FLOAT_LIKE_INPUT_TYPES = frozenset({"FLOAT", "NUMBER"})
_NON_RESOURCE_SIGNAL_TYPES: Final[frozenset[str]] = frozenset(
    {
        "ANY",
        "BOOLEAN",
        "COMBO",
        "FLOAT",
        "IMAGE",
        "INT",
        "INTEGER",
        "LATENT",
        "LIST",
        "MASK",
        "NUMBER",
        "STRING",
    }
)


def _combined_input_definitions(
    node_definition: Mapping[str, object] | None,
) -> dict[str, object]:
    """Return required and optional Comfy input definitions keyed by input name."""

    if not isinstance(node_definition, Mapping):
        return {}
    input_section_raw = node_definition.get("input")
    input_section = input_section_raw if isinstance(input_section_raw, Mapping) else {}
    combined_inputs: dict[str, object] = {}
    for section_name in ("required", "optional"):
        section_raw = input_section.get(section_name)
        if not isinstance(section_raw, Mapping):
            continue
        combined_inputs.update(
            (key, value) for key, value in section_raw.items() if isinstance(key, str)
        )
    return combined_inputs


def _normalized_input_name(value: str) -> str:
    """Return the normalized input name used by structural heuristics."""

    return value.strip().lower()


def _input_type_name(input_definition: object) -> str | None:
    """Return the normalized Comfy type name from one input definition."""

    if not isinstance(input_definition, list) or not input_definition:
        return None
    type_name = input_definition[0]
    if not isinstance(type_name, str):
        return None
    return type_name.strip().upper()


def _input_definition_has_type(
    input_definition: object,
    *,
    allowed_types: frozenset[str],
) -> bool:
    """Return whether one input definition declares an allowed scalar type."""

    type_name = _input_type_name(input_definition)
    return type_name in allowed_types


def infer_model_patch_switch(node_definition: Mapping[str, object] | None) -> bool:
    """Return whether a node definition looks like a MODEL in/out patch node."""

    return "MODEL" in infer_typed_transform_signal_types(node_definition)


def _resource_signal_type(type_name: str | None) -> str | None:
    """Return a normalized resource/config signal type when one is inferable."""

    if type_name is None:
        return None
    normalized = type_name.strip().upper()
    if not normalized or normalized in _NON_RESOURCE_SIGNAL_TYPES:
        return None
    return normalized


def _output_type_names(node_definition: Mapping[str, object]) -> frozenset[str]:
    """Return normalized output type names declared by one live node definition."""

    outputs_raw = node_definition.get("output")
    outputs = outputs_raw if isinstance(outputs_raw, list) else []
    return frozenset(
        output.strip().upper()
        for output in outputs
        if isinstance(output, str) and output.strip()
    )


def infer_typed_transform_signal_types(
    node_definition: Mapping[str, object] | None,
) -> frozenset[str]:
    """Return resource/config signal types that pass through a node definition."""

    if not isinstance(node_definition, Mapping):
        return frozenset()

    input_signals = frozenset(
        signal
        for signal in (
            _resource_signal_type(_input_type_name(candidate))
            for candidate in _combined_input_definitions(node_definition).values()
        )
        if signal is not None
    )
    output_signals = frozenset(
        signal
        for signal in (
            _resource_signal_type(output_type)
            for output_type in _output_type_names(node_definition)
        )
        if signal is not None
    )
    return input_signals & output_signals


def infer_sampler_worker_node(
    node_definition: Mapping[str, object] | None,
    *,
    input_keys: tuple[str, ...] = (),
) -> bool:
    """Return whether inputs identify a sampler-like primary worker node."""

    definitions = _combined_input_definitions(node_definition)
    normalized_definitions = {
        _normalized_input_name(key): value for key, value in definitions.items()
    }
    normalized_input_names = {
        *normalized_definitions.keys(),
        *(_normalized_input_name(key) for key in input_keys),
    }
    if not _SAMPLER_WORKER_INPUTS.issubset(normalized_input_names):
        return False
    if "steps" in normalized_definitions and not _input_definition_has_type(
        normalized_definitions["steps"],
        allowed_types=_INTEGER_LIKE_INPUT_TYPES,
    ):
        return False
    if "denoise" in normalized_definitions and not _input_definition_has_type(
        normalized_definitions["denoise"],
        allowed_types=_FLOAT_LIKE_INPUT_TYPES,
    ):
        return False
    return True


def normalize_prompt_label(value: str) -> str:
    """Return the normalized prompt-role label used for exact matching."""

    normalized = value.strip().lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized)


def prompt_role_from_label(value: str | None) -> PromptRole | None:
    """Return the prompt role declared by an exact normalized node label."""

    if value is None:
        return None
    normalized = normalize_prompt_label(value)
    if normalized == "positive prompt":
        return PromptRole.POSITIVE
    if normalized == "negative prompt":
        return PromptRole.NEGATIVE
    return None


def multiline_string_input_keys(
    node_definition: Mapping[str, object] | None,
    input_keys: tuple[str, ...],
) -> tuple[str, ...]:
    """Return ordered input keys for multiline Comfy STRING fields."""

    combined_inputs = _combined_input_definitions(node_definition)
    candidates: list[str] = []
    for input_key in input_keys:
        raw_info = combined_inputs.get(input_key)
        if not isinstance(raw_info, list) or len(raw_info) < 2:
            continue
        type_name = raw_info[0]
        metadata = raw_info[1]
        if not isinstance(type_name, str) or type_name.upper() != "STRING":
            continue
        if not isinstance(metadata, Mapping) or metadata.get("multiline") is not True:
            continue
        candidates.append(input_key)
    return tuple(candidates)


def infer_node_behavior_patch(
    node_definition: Mapping[str, object] | None,
    *,
    node_title: str | None = None,
    input_keys: tuple[str, ...] = (),
) -> NodeBehaviorPatch:
    """Return the built-in inference patch for one live node definition."""

    _ = node_title
    if infer_sampler_worker_node(node_definition, input_keys=input_keys):
        return NodeBehaviorPatch(
            card=CardBehaviorPatch(
                enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                enabled_switch_source=ActivationSwitchSource.INFERRED,
                activation_switch_role=ActivationSwitchRole.SAMPLER_WORKER,
                icon_name="application",
            ),
        )
    activation_signal_types = infer_typed_transform_signal_types(node_definition)
    if activation_signal_types:
        return NodeBehaviorPatch(
            card=CardBehaviorPatch(
                enabled_switch_policy=EnabledSwitchPolicy.ALWAYS,
                enabled_switch_source=ActivationSwitchSource.INFERRED,
                activation_switch_role=ActivationSwitchRole.TYPED_TRANSFORM,
                activation_signal_types=activation_signal_types,
            ),
        )
    return NodeBehaviorPatch()


__all__ = [
    "infer_model_patch_switch",
    "infer_node_behavior_patch",
    "infer_sampler_worker_node",
    "infer_typed_transform_signal_types",
    "multiline_string_input_keys",
    "normalize_prompt_label",
    "prompt_role_from_label",
]
