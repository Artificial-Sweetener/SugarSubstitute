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

"""Share reusable Sugar serialization state within one preparation request."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from substitute.application.recipes.model_hash_lookup import RecipeModelHashLookup
from substitute.application.recipes.prompt_lora_hash_lookup import PromptLoraHashLookup
from substitute.application.recipes.sugar_label_resolution import SugarScriptLabelIndex
from substitute.domain.common import JsonObject, JsonValue
from substitute.domain.recipes.sugar_ast import SugarBufferMap

RecipeFieldKey: TypeAlias = tuple[str, str, str]
RecipePromptFieldOverrides: TypeAlias = Mapping[RecipeFieldKey, JsonValue]


@dataclass(frozen=True, slots=True)
class RecipeSerializationPlan:
    """Precompute reusable Sugar serialization inputs for one captured workflow."""

    ordered_aliases: tuple[str, ...]
    base_stripped_buffers: SugarBufferMap
    base_prepared_buffers: SugarBufferMap
    label_index: SugarScriptLabelIndex
    model_hashes_by_field: Mapping[RecipeFieldKey, str]


@dataclass(slots=True)
class RecipeSerializationContext:
    """Cache recipe serialization metadata within one generation request."""

    model_hash_lookup: RecipeModelHashLookup | None = None
    prompt_lora_hash_lookup: PromptLoraHashLookup | None = None
    required_node_definitions_by_class: dict[str, JsonObject] = field(
        default_factory=dict
    )
    prompt_lora_hashes_by_text: dict[str, OrderedDict[str, str]] = field(
        default_factory=dict
    )
    prompt_lora_sha_by_normalized_name: dict[str, str | None] = field(
        default_factory=dict
    )


def buffers_with_prompt_field_overrides(
    *,
    base_buffers: SugarBufferMap,
    prompt_field_overrides: RecipePromptFieldOverrides | None,
) -> SugarBufferMap:
    """Return buffers with prompt input overrides applied using structural sharing."""

    if not prompt_field_overrides:
        return base_buffers
    buffers: SugarBufferMap = OrderedDict(base_buffers.items())
    copied_aliases: set[str] = set()
    copied_node_maps: set[str] = set()
    copied_nodes: set[tuple[str, str]] = set()
    for (alias, node_name, field_key), override_value in prompt_field_overrides.items():
        if alias not in copied_aliases:
            buffers[alias] = OrderedDict(base_buffers[alias].items())
            copied_aliases.add(alias)
        buffer = buffers[alias]
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            continue
        if alias not in copied_node_maps:
            buffer["nodes"] = dict(nodes.items())
            copied_node_maps.add(alias)
        node_map = buffer["nodes"]
        if not isinstance(node_map, dict):
            continue
        node = node_map.get(node_name)
        if not isinstance(node, Mapping):
            continue
        node_key = (alias, node_name)
        if node_key not in copied_nodes:
            node_map[node_name] = dict(node.items())
            copied_nodes.add(node_key)
        copied_node = node_map[node_name]
        if not isinstance(copied_node, dict):
            continue
        inputs = copied_node.get("inputs")
        if not isinstance(inputs, Mapping):
            inputs = {}
        copied_node["inputs"] = dict(inputs.items())
        copied_inputs = copied_node["inputs"]
        if isinstance(copied_inputs, dict):
            copied_inputs[field_key] = override_value
    return buffers


__all__ = [
    "RecipeFieldKey",
    "RecipePromptFieldOverrides",
    "RecipeSerializationContext",
    "RecipeSerializationPlan",
    "buffers_with_prompt_field_overrides",
]
