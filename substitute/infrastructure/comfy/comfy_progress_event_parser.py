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

"""Parse and normalize Comfy progress event fields without UI dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Callable, Literal, cast

from substitute.application.ports.comfy_gateway import ModelLoadProgressUpdate
from substitute.domain.common import WorkflowId

NodeProgressState = Literal["pending", "running", "finished", "error"]
ModelLoadSourceMetadataResolver = Callable[
    [str, set[str]],
    tuple[str | None, str | None],
]


@dataclass(frozen=True)
class ComfyNodeProgressState:
    """Represent one node entry from Comfy's progress_state websocket event."""

    node_id: str
    owner_node_id: str | None
    state: NodeProgressState
    value: float
    maximum: float


def fraction_from_progress_data(data: Mapping[str, object]) -> float | None:
    """Return fractional progress from a Comfy progress event."""

    value = numeric_value(data.get("value"))
    maximum = numeric_value(data.get("max"))
    if value is None or maximum is None:
        return None
    return fraction_from_values(value=value, maximum=maximum)


def fraction_from_values(*, value: float, maximum: float) -> float | None:
    """Return a bounded fraction from progress values."""

    if maximum <= 0:
        return None
    return min(1.0, max(0.0, value / maximum))


def compute_sampler_percent(data: Mapping[str, object]) -> float | None:
    """Compute sampler percentage from progress message payload."""

    node_id = data.get("node")
    current = data.get("value")
    maximum = data.get("max")
    if node_id is None or current is None or maximum is None:
        return None
    if isinstance(current, (int, float)) and isinstance(maximum, (int, float)):
        if maximum <= 0:
            return None
        return clamp_percent(100.0 * float(current) / float(maximum))
    return None


def optional_percent(value: object) -> float | None:
    """Return an optional clamped percentage."""

    if not isinstance(value, (int, float)):
        return None
    return clamp_percent(float(value))


def clamp_percent(value: float) -> float:
    """Clamp raw percentage values to the UI progress range."""

    return min(100.0, max(0.0, value))


def numeric_value(value: object) -> float | None:
    """Return a float value for numeric websocket fields."""

    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def parse_progress_state_nodes(
    *,
    data: Mapping[str, object],
    all_node_ids: set[str],
) -> tuple[ComfyNodeProgressState, ...]:
    """Parse Comfy progress_state nodes into normalized progress entries."""

    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return ()

    parsed: list[ComfyNodeProgressState] = []
    for raw_node_id, raw_state in nodes.items():
        if not isinstance(raw_state, dict):
            continue
        state_value = raw_state.get("state")
        if state_value not in {"pending", "running", "finished", "error"}:
            continue
        value = raw_state.get("value")
        maximum = raw_state.get("max")
        if not isinstance(value, (int, float)) or not isinstance(maximum, (int, float)):
            continue
        node_id = _string_or_none(raw_state.get("node_id")) or str(raw_node_id)
        owner_node_id = normalize_node_id(
            node_id=node_id,
            all_node_ids=all_node_ids,
            display_node_id=_string_or_none(raw_state.get("display_node_id")),
            parent_node_id=_string_or_none(raw_state.get("parent_node_id")),
            real_node_id=_string_or_none(raw_state.get("real_node_id")),
        )
        parsed.append(
            ComfyNodeProgressState(
                node_id=node_id,
                owner_node_id=owner_node_id,
                state=cast(NodeProgressState, state_value),
                value=float(value),
                maximum=float(maximum),
            )
        )
    return tuple(parsed)


def sampler_percent_from_progress_state(
    *,
    progress_states: tuple[ComfyNodeProgressState, ...],
    prompt_nodes: Mapping[str, object],
) -> float | None:
    """Return the most advanced running sampler progress_state percentage."""

    sampler_percents: list[float] = []
    for progress_state in progress_states:
        if progress_state.state != "running":
            continue
        if progress_state.owner_node_id is None:
            continue
        if progress_state.maximum <= 0:
            continue
        if not is_sampler_node(progress_state.owner_node_id, prompt_nodes):
            continue
        sampler_percents.append(
            clamp_percent(100.0 * progress_state.value / progress_state.maximum)
        )
    if not sampler_percents:
        return None
    return max(sampler_percents)


def parse_model_load_progress(
    *,
    data: Mapping[str, object],
    workflow_id: WorkflowId,
    active_prompt_id: str | None,
    all_node_ids: set[str],
    source_metadata_resolver: ModelLoadSourceMetadataResolver,
) -> ModelLoadProgressUpdate | None:
    """Parse Substitute BackEnd model-load telemetry into a typed update."""

    version = data.get("version")
    if version != 1:
        return None
    prompt_id = _string_or_none(data.get("prompt_id"))
    phase = data.get("phase")
    state = data.get("state")
    if not isinstance(phase, str) or not isinstance(state, str):
        return None
    if phase not in {
        "requested",
        "dynamic_vram_staging",
        "loaded_partially",
        "loaded_completely",
        "failed",
    }:
        return None
    if state not in {"running", "finished", "unknown"}:
        return None
    if prompt_id is not None and prompt_id != active_prompt_id:
        return None
    node_id = _string_or_none(data.get("node_id"))
    display_node_id = _string_or_none(data.get("display_node_id"))
    owner_node_id = (
        normalize_node_id(
            node_id=node_id,
            all_node_ids=all_node_ids,
            display_node_id=display_node_id,
        )
        if node_id is not None
        else display_node_id
        if display_node_id in all_node_ids
        else None
    )
    if prompt_id is None and owner_node_id is None:
        return None
    source_node_id = _strict_string_or_none(data.get("source_node_id"))
    source_input_key = _strict_string_or_none(data.get("source_input_key"))
    source_cube_alias: str | None = None
    source_workflow_node_name: str | None = None
    if source_node_id is not None and source_input_key is not None:
        source_cube_alias, source_workflow_node_name = source_metadata_resolver(
            source_node_id,
            all_node_ids,
        )
    return ModelLoadProgressUpdate(
        workflow_id=workflow_id,
        prompt_id=prompt_id,
        node_id=node_id,
        display_node_id=owner_node_id or display_node_id,
        phase=phase,
        state=state,
        percent=optional_percent(data.get("percent")),
        value=_optional_float(data.get("value")),
        maximum=_optional_float(data.get("max")),
        unit=_string_or_none(data.get("unit")),
        model_class=_string_or_none(data.get("model_class")),
        model_name=_string_or_none(data.get("model_name")),
        source_node_id=source_node_id,
        source_input_key=source_input_key,
        source_cube_alias=source_cube_alias,
        source_workflow_node_name=source_workflow_node_name,
        detail=_string_or_none(data.get("detail")),
    )


def is_sampler_node(node_id: str, prompt_nodes: Mapping[str, object]) -> bool:
    """Return whether a prompt node should drive sampler progress."""

    node_data = prompt_nodes.get(node_id)
    if not isinstance(node_data, dict):
        return False
    class_type = node_data.get("class_type")
    return isinstance(class_type, str) and "sampler" in class_type.lower()


def normalize_node_id(
    *,
    node_id: str | None,
    all_node_ids: set[str],
    display_node_id: str | None = None,
    parent_node_id: str | None = None,
    real_node_id: str | None = None,
) -> str | None:
    """Return the queued workflow node that owns a Comfy execution node."""

    for candidate in (display_node_id, node_id, parent_node_id, real_node_id):
        if candidate in all_node_ids:
            return candidate
    if node_id is not None:
        dotted_owner = node_id.split(".", 1)[0]
        if dotted_owner in all_node_ids:
            return dotted_owner
        colon_owner = node_id.split(":", 1)[0]
        if colon_owner in all_node_ids:
            return colon_owner
    return None


def _string_or_none(value: object) -> str | None:
    """Return string values while preserving missing optional fields."""

    if isinstance(value, (str, int)):
        return str(value)
    return None


def _strict_string_or_none(value: object) -> str | None:
    """Return non-empty string values without coercing malformed payload fields."""

    if isinstance(value, str) and value:
        return value
    return None


def _optional_float(value: object) -> float | None:
    """Return numeric payload fields as floats when present."""

    if isinstance(value, (int, float)):
        return float(value)
    return None


__all__ = [
    "clamp_percent",
    "ComfyNodeProgressState",
    "compute_sampler_percent",
    "fraction_from_progress_data",
    "fraction_from_values",
    "is_sampler_node",
    "ModelLoadSourceMetadataResolver",
    "normalize_node_id",
    "numeric_value",
    "optional_percent",
    "parse_model_load_progress",
    "parse_progress_state_nodes",
    "sampler_percent_from_progress_state",
]
