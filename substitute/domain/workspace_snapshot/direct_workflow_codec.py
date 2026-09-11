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

"""Persist one complete native Comfy workflow document losslessly."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.common import JsonObject

from .errors import SnapshotCodecError
from .json_value_codec import json_object_to_json, json_value_to_json


def direct_workflow_to_json(
    state: DirectWorkflowState | None,
    *,
    cube_projection_state: JsonObject | None = None,
) -> JsonObject | None:
    """Return durable graph state without runtime-only editor objects."""

    if state is None:
        return None
    source_workflow = deepcopy(state.source_workflow)
    return {
        "source_path": str(state.source_path),
        "source_workflow": json_object_to_json(
            source_workflow,
            path="workflow.direct_workflow.source_workflow",
        ),
        "buffer": json_object_to_json(
            state.buffer,
            path="workflow.direct_workflow.buffer",
        ),
        "ui": {
            key: json_value_to_json(
                value,
                path=f"workflow.direct_workflow.ui.{key}",
            )
            for key, value in state.ui.items()
            if key != "node_behavior_runtime"
        },
        "dirty": state.dirty,
        "cube_projection_state": json_object_to_json(
            cube_projection_state
            if cube_projection_state is not None
            else state.cube_projection_state,
            path="workflow.direct_workflow.cube_projection_state",
        ),
    }


def direct_workflow_from_json(value: object) -> DirectWorkflowState | None:
    """Build optional native graph state from a persisted workflow payload."""

    if value is None:
        return None
    payload = _required_mapping(value)
    source_path = payload.get("source_path")
    if not isinstance(source_path, str):
        raise SnapshotCodecError("Missing or invalid string field: source_path")
    return DirectWorkflowState(
        source_path=Path(source_path),
        source_workflow=dict(_required_mapping(payload.get("source_workflow"))),
        buffer=dict(_required_mapping(payload.get("buffer"))),
        ui=dict(_optional_mapping(payload.get("ui"))),
        dirty=payload.get("dirty") is True,
        cube_projection_state=dict(
            _optional_mapping(payload.get("cube_projection_state"))
        ),
    )


def _required_mapping(value: object) -> Mapping[str, object]:
    """Return one decoded object or raise a snapshot boundary error."""

    if not isinstance(value, Mapping):
        raise SnapshotCodecError("Expected JSON object")
    return value


def _optional_mapping(value: object) -> Mapping[str, object]:
    """Return one optional decoded object."""

    return {} if value is None else _required_mapping(value)


__all__ = ["direct_workflow_from_json", "direct_workflow_to_json"]
