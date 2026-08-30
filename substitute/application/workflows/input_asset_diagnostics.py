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

"""Emit structured diagnostics for authored and compiled input assets."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import TypeVar

from substitute.application.recipes.workflow_payload_nodes import (
    executable_prompt_nodes,
)
from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)
from substitute.domain.common import WorkflowId
from substitute.shared.logging.logger import get_logger, log_debug

_GENERATION_LOGGER = get_logger("application.generation.generation_service")
_RECIPE_LOGGER = get_logger("application.recipes.recipe_io_service")
_NodeKey = TypeVar("_NodeKey")


def log_generation_payload_assets(
    workflow_payload: dict[str, object],
    *,
    workflow_id: WorkflowId,
    workflow_name: str,
    stage: str,
) -> None:
    """Log known asset fields in one compiled or staged execution payload."""

    _log_node_assets(
        executable_prompt_nodes(workflow_payload),
        logger=_GENERATION_LOGGER,
        event="Generation payload image input",
        context={
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "stage": stage,
        },
    )


def log_recipe_buffer_assets(
    *,
    stripped_buffers: Mapping[str, Mapping[str, object]],
    ordered_aliases: Sequence[str],
) -> None:
    """Log known asset fields in buffers immediately before Sugar encoding."""

    for cube_alias in ordered_aliases:
        buffer = stripped_buffers.get(cube_alias, {})
        nodes = buffer.get("nodes", {})
        if not isinstance(nodes, Mapping):
            continue
        _log_node_assets(
            nodes,
            logger=_RECIPE_LOGGER,
            event="Serializing workflow image input",
            context={
                "ordered_aliases": tuple(ordered_aliases),
                "cube_alias": cube_alias,
            },
        )


def _log_node_assets(
    nodes: Mapping[_NodeKey, object],
    *,
    logger: logging.Logger,
    event: str,
    context: Mapping[str, object],
) -> None:
    """Log fields recognized by the authoritative asset semantics owner."""

    field_policy = InputAssetFieldPolicy()
    for node_name, node_data in nodes.items():
        if not isinstance(node_data, Mapping):
            continue
        class_type = node_data.get("class_type")
        if not isinstance(class_type, str):
            continue
        inputs = node_data.get("inputs", {})
        for asset_field in field_policy.fields_for_node(class_type, {}):
            asset_value = (
                inputs.get(asset_field.field_key)
                if isinstance(inputs, Mapping)
                else None
            )
            log_debug(
                logger,
                event,
                **context,
                node_name=str(node_name),
                node_class=class_type,
                field_key=asset_field.field_key,
                image_value=asset_value,
            )


__all__ = ["log_generation_payload_assets", "log_recipe_buffer_assets"]
