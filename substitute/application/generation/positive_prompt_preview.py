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

"""Extract safe Positive Prompt previews for queued generation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from textwrap import wrap
from typing import cast

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.domain.node_behavior import PromptRole


_DEFAULT_PROMPT_PREVIEW_LIMIT = 200
_PROMPT_PREVIEW_LINE_WIDTH = 72


def prompt_preview_text(
    value: object,
    *,
    limit: int = _DEFAULT_PROMPT_PREVIEW_LIMIT,
) -> str | None:
    """Return normalized prompt preview text capped for queue tooltips."""

    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    preview = normalized
    if len(normalized) > limit:
        preview = f"{normalized[: max(0, limit - 3)].rstrip()}..."
    return "\n".join(wrap(preview, width=_PROMPT_PREVIEW_LINE_WIDTH)) or None


def positive_prompt_preview_from_workflow(
    *,
    workflow: object,
    behavior_snapshot: EditorBehaviorSnapshot | None,
    limit: int = _DEFAULT_PROMPT_PREVIEW_LIMIT,
) -> str | None:
    """Return the first semantic Positive Prompt preview for a workflow."""

    if behavior_snapshot is None:
        return None

    stack_order = _workflow_stack_order(workflow)
    cubes = _workflow_cubes(workflow)
    if stack_order is None or cubes is None:
        return None

    endpoint_index = behavior_snapshot.prompt_endpoint_index
    for cube_alias in stack_order:
        endpoint = endpoint_index.endpoint_for(cube_alias, PromptRole.POSITIVE)
        if endpoint is None:
            continue
        cube_state = cubes.get(endpoint.cube_alias)
        if cube_state is None:
            continue
        raw_value = _input_value(
            cube_state,
            node_name=endpoint.node_name,
            field_key=endpoint.field_key,
        )
        return prompt_preview_text(raw_value, limit=limit)
    return None


def positive_prompt_preview_from_prompt_overrides(
    *,
    workflow: object,
    behavior_snapshot: EditorBehaviorSnapshot | None,
    prompt_field_overrides: Mapping[tuple[str, str, str], object],
    limit: int = _DEFAULT_PROMPT_PREVIEW_LIMIT,
) -> str | None:
    """Return the first Positive Prompt preview using prompt-field overrides."""

    if behavior_snapshot is None:
        return None

    stack_order = _workflow_stack_order(workflow)
    cubes = _workflow_cubes(workflow)
    if stack_order is None or cubes is None:
        return None

    endpoint_index = behavior_snapshot.prompt_endpoint_index
    for cube_alias in stack_order:
        endpoint = endpoint_index.endpoint_for(cube_alias, PromptRole.POSITIVE)
        if endpoint is None:
            continue
        field_key = (endpoint.cube_alias, endpoint.node_name, endpoint.field_key)
        if field_key in prompt_field_overrides:
            return prompt_preview_text(prompt_field_overrides[field_key], limit=limit)
        cube_state = cubes.get(endpoint.cube_alias)
        if cube_state is None:
            continue
        raw_value = _input_value(
            cube_state,
            node_name=endpoint.node_name,
            field_key=endpoint.field_key,
        )
        return prompt_preview_text(raw_value, limit=limit)
    return None


def _workflow_stack_order(workflow: object) -> tuple[str, ...] | None:
    """Return workflow stack order when it is available as strings."""

    raw_stack_order = getattr(workflow, "stack_order", None)
    if isinstance(raw_stack_order, Sequence) and not isinstance(raw_stack_order, str):
        return tuple(alias for alias in raw_stack_order if isinstance(alias, str))
    return None


def _workflow_cubes(workflow: object) -> Mapping[str, object] | None:
    """Return workflow cubes when they are available as a mapping."""

    raw_cubes = getattr(workflow, "cubes", None)
    if isinstance(raw_cubes, Mapping):
        return cast(Mapping[str, object], raw_cubes)
    return None


def _input_value(cube_state: object, *, node_name: str, field_key: str) -> object:
    """Return one node input value from a cube state without assuming shape."""

    buffer = getattr(cube_state, "buffer", None)
    if not isinstance(buffer, Mapping):
        return None
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(node_name)
    if not isinstance(node, Mapping):
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return None
    return inputs.get(field_key)


__all__ = [
    "positive_prompt_preview_from_prompt_overrides",
    "positive_prompt_preview_from_workflow",
    "prompt_preview_text",
]
