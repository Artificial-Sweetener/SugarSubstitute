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

"""Restore authored node inputs after schema-aware cube buffer merging.

Cube package definitions intentionally omit local model selections so authored cube
packages stay portable across machines. Restored workflows and sessions are
different: their node inputs are user-authored runtime state and must survive cube
materialization even when the static cube definition does not declare every live
Comfy model field.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import cast

from substitute.domain.common import JsonObject

MODEL_INPUT_KEYS = frozenset(
    {
        "ckpt_name",
        "checkpoint",
        "checkpoint_name",
        "model_name",
        "vae_name",
        "lora_name",
        "unet_name",
        "clip_name",
        "clip_name1",
        "clip_name2",
        "control_net_name",
        "diffusion_model",
    }
)


@dataclass(frozen=True, slots=True)
class PersistedInputOverlayResult:
    """Summarize restore/import input overlay work for logging and tests."""

    restored_node_count: int = 0
    restored_input_count: int = 0
    restored_model_field_count: int = 0
    skipped_missing_node_count: int = 0
    skipped_class_mismatch_count: int = 0


def overlay_persisted_node_inputs(
    *,
    cube_buffer: JsonObject,
    buffer_patch: object,
) -> PersistedInputOverlayResult:
    """Restore persisted input values for nodes already present in a runtime buffer."""

    if not isinstance(buffer_patch, Mapping):
        return PersistedInputOverlayResult()
    persisted_nodes = buffer_patch.get("nodes")
    runtime_nodes = cube_buffer.get("nodes")
    if not isinstance(persisted_nodes, Mapping) or not isinstance(
        runtime_nodes, MutableMapping
    ):
        return PersistedInputOverlayResult()

    restored_node_count = 0
    restored_input_count = 0
    skipped_missing_node_count = 0
    skipped_class_mismatch_count = 0
    restored_model_field_count = 0

    for node_name, persisted_node in persisted_nodes.items():
        if not isinstance(node_name, str) or not isinstance(persisted_node, Mapping):
            continue
        runtime_node = runtime_nodes.get(node_name)
        if not isinstance(runtime_node, MutableMapping):
            skipped_missing_node_count += 1
            continue
        if _has_class_mismatch(runtime_node, persisted_node):
            skipped_class_mismatch_count += 1
            continue

        persisted_inputs = persisted_node.get("inputs")
        if not isinstance(persisted_inputs, Mapping):
            continue
        runtime_inputs = _ensure_runtime_inputs(runtime_node)
        node_input_count = 0
        for field_key, value in persisted_inputs.items():
            if not isinstance(field_key, str):
                continue
            copied_value = copy.deepcopy(value)
            runtime_inputs[field_key] = copied_value
            restored_input_count += 1
            node_input_count += 1
            if field_key in MODEL_INPUT_KEYS:
                restored_model_field_count += 1
        if node_input_count:
            restored_node_count += 1

    return PersistedInputOverlayResult(
        restored_node_count=restored_node_count,
        restored_input_count=restored_input_count,
        restored_model_field_count=restored_model_field_count,
        skipped_missing_node_count=skipped_missing_node_count,
        skipped_class_mismatch_count=skipped_class_mismatch_count,
    )


def _has_class_mismatch(
    runtime_node: Mapping[str, object],
    persisted_node: Mapping[object, object],
) -> bool:
    """Return whether two node payloads declare different string class types."""

    runtime_class = runtime_node.get("class_type")
    persisted_class = persisted_node.get("class_type")
    return (
        isinstance(runtime_class, str)
        and isinstance(persisted_class, str)
        and runtime_class != persisted_class
    )


def _ensure_runtime_inputs(
    runtime_node: MutableMapping[str, object],
) -> MutableMapping[str, object]:
    """Return mutable runtime inputs, creating them on an existing node if absent."""

    runtime_inputs = runtime_node.get("inputs")
    if isinstance(runtime_inputs, MutableMapping):
        return cast(MutableMapping[str, object], runtime_inputs)
    created_inputs: dict[str, object] = {}
    runtime_node["inputs"] = created_inputs
    return created_inputs


__all__ = [
    "MODEL_INPUT_KEYS",
    "PersistedInputOverlayResult",
    "overlay_persisted_node_inputs",
]
