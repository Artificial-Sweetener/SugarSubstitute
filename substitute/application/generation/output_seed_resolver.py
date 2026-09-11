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

"""Resolve the output path seed token from prepared generation inputs."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.domain.common import JsonObject


def resolve_output_seed(
    *,
    workflow: object | None,
    workflow_payload: JsonObject,
) -> str:
    """Return the preferred output seed token value for one generation."""

    global_seed = _global_override_seed(workflow)
    if global_seed:
        return global_seed
    return _first_workflow_seed(workflow_payload)


def _global_override_seed(workflow: object | None) -> str:
    """Return the selected global seed directly from workflow state."""

    overrides = getattr(workflow, "global_overrides", None)
    if not isinstance(overrides, Mapping):
        return ""
    override = overrides.get("seed")
    if not isinstance(override, Mapping) or "value" not in override:
        return ""
    return _seed_value_text(override.get("value"))


def _first_workflow_seed(workflow_payload: JsonObject) -> str:
    """Return the first exact workflow input seed, if present."""

    for node in executable_prompt_nodes(workflow_payload).values():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping) or "seed" not in inputs:
            continue
        seed_text = _seed_value_text(inputs.get("seed"))
        if seed_text:
            return seed_text
    definitions = workflow_payload.get("definitions")
    if isinstance(definitions, Mapping):
        subgraphs = definitions.get("subgraphs")
        if isinstance(subgraphs, list):
            for definition in subgraphs:
                seed_text = _embedded_definition_seed(definition)
                if seed_text:
                    return seed_text
    return ""


def _embedded_definition_seed(value: object) -> str:
    """Read the first seed from one embedded canonical Cube document."""

    if not isinstance(value, Mapping):
        return ""
    extra = value.get("extra")
    document = extra.get("sugarcubes_document") if isinstance(extra, Mapping) else None
    implementation = (
        document.get("implementation") if isinstance(document, Mapping) else None
    )
    nodes = implementation.get("nodes") if isinstance(implementation, Mapping) else None
    if not isinstance(nodes, Mapping):
        return ""
    for node in nodes.values():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, Mapping) and "seed" in inputs:
            seed_text = _seed_value_text(inputs.get("seed"))
            if seed_text:
                return seed_text
    return ""


def _seed_value_text(value: object) -> str:
    """Return filename-token text for supported scalar seed values."""

    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


__all__ = ["resolve_output_seed"]
