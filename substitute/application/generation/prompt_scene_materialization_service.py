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

"""Materialize text-authored prompt scenes into generation-only workflow copies."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from copy import deepcopy
from typing import Any, Protocol, TypeVar, cast

from substitute.application.prompt_editor import WorkflowSceneAnalysis
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.prompt import (
    materialize_scene_prompt,
    parse_prompt_scene_document,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.generation.prompt_scene_materialization_service")


class PromptSceneMaterializationCube(Protocol):
    """Describe cube state required for prompt scene materialization."""

    buffer: Any


class PromptSceneMaterializationWorkflow(Protocol):
    """Describe workflow state required for prompt scene materialization."""

    @property
    def stack_order(self) -> Sequence[str]:
        """Return cube aliases in workflow order."""
        ...

    @property
    def cubes(self) -> Mapping[str, PromptSceneMaterializationCube]:
        """Return cube states keyed by alias."""
        ...


_WorkflowT = TypeVar("_WorkflowT", bound=PromptSceneMaterializationWorkflow)


class PromptSceneMaterializationService:
    """Create generation-only workflow copies for one runnable scene."""

    def materialize_workflow_for_scene(
        self,
        *,
        workflow: _WorkflowT,
        workflow_id: str,
        scene_key: str,
        endpoint_index: PromptEndpointIndex,
        scene_analysis: WorkflowSceneAnalysis,
    ) -> _WorkflowT:
        """Return a copied workflow whose independent prompts target one scene."""

        if scene_key not in {scene.key for scene in scene_analysis.scenes}:
            raise ValueError(f"Unknown workflow scene key: {scene_key}")

        workflow_copy = deepcopy(workflow)
        for endpoint in endpoint_index.endpoints:
            if not endpoint.linkable:
                continue
            if _endpoint_has_active_prompt_link(workflow_copy, endpoint):
                log_debug(
                    _LOGGER,
                    "Skipped linked prompt endpoint during scene materialization",
                    workflow_id=workflow_id,
                    cube_alias=endpoint.cube_alias,
                    node_name=endpoint.node_name,
                    field_key=endpoint.field_key,
                    scene_key=scene_key,
                )
                continue
            self._materialize_endpoint(
                workflow=workflow_copy,
                workflow_id=workflow_id,
                endpoint=endpoint,
                scene_key=scene_key,
            )
        return workflow_copy

    @staticmethod
    def _materialize_endpoint(
        *,
        workflow: PromptSceneMaterializationWorkflow,
        workflow_id: str,
        endpoint: PromptEndpoint,
        scene_key: str,
    ) -> None:
        """Replace one endpoint prompt with universal text plus matching scene text."""

        current_text = _endpoint_prompt_text(workflow, endpoint)
        document = parse_prompt_scene_document(current_text)
        scene_block = document.first_scene_for_key(scene_key)
        materialized = materialize_scene_prompt(
            universal_text=document.universal_text,
            scene_text="" if scene_block is None else scene_block.text,
        )
        if not _set_endpoint_prompt_text(workflow, endpoint, materialized):
            log_warning(
                _LOGGER,
                "Failed to materialize prompt scene endpoint",
                workflow_id=workflow_id,
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
                field_key=endpoint.field_key,
                scene_key=scene_key,
            )
            return
        log_debug(
            _LOGGER,
            "Materialized prompt scene endpoint",
            workflow_id=workflow_id,
            cube_alias=endpoint.cube_alias,
            node_name=endpoint.node_name,
            field_key=endpoint.field_key,
            scene_key=scene_key,
            had_matching_scene=scene_block is not None,
        )


def _endpoint_prompt_text(
    workflow: PromptSceneMaterializationWorkflow,
    endpoint: PromptEndpoint,
) -> str:
    """Return prompt text stored at one endpoint, or an empty string if missing."""

    inputs = _endpoint_inputs(workflow, endpoint)
    if inputs is None:
        return ""
    value = inputs.get(endpoint.field_key)
    return value if isinstance(value, str) else ""


def _set_endpoint_prompt_text(
    workflow: PromptSceneMaterializationWorkflow,
    endpoint: PromptEndpoint,
    value: str,
) -> bool:
    """Set prompt text at one endpoint when its mutable input mapping exists."""

    inputs = _endpoint_inputs(workflow, endpoint)
    if inputs is None:
        return False
    inputs[endpoint.field_key] = value
    return True


def _endpoint_inputs(
    workflow: PromptSceneMaterializationWorkflow,
    endpoint: PromptEndpoint,
) -> MutableMapping[str, object] | None:
    """Return mutable node inputs for one endpoint when available."""

    node = _endpoint_node(workflow, endpoint)
    if node is None:
        return None
    inputs = node.get("inputs")
    if not isinstance(inputs, MutableMapping):
        return None
    return cast(MutableMapping[str, object], inputs)


def _endpoint_has_active_prompt_link(
    workflow: PromptSceneMaterializationWorkflow,
    endpoint: PromptEndpoint,
) -> bool:
    """Return whether one endpoint is governed by existing prompt linking."""

    node = _endpoint_node(workflow, endpoint)
    if node is None:
        return False
    for link_key in ("node_link", "prompt_link"):
        link = node.get(link_key)
        if not isinstance(link, Mapping):
            continue
        if link.get("from_cube") is not None:
            return True
    return False


def _endpoint_node(
    workflow: PromptSceneMaterializationWorkflow,
    endpoint: PromptEndpoint,
) -> MutableMapping[str, object] | None:
    """Return mutable node payload for one endpoint when available."""

    cube = workflow.cubes.get(endpoint.cube_alias)
    if cube is None:
        return None
    buffer = getattr(cube, "buffer", None)
    if not isinstance(buffer, Mapping):
        return None
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return None
    node = nodes.get(endpoint.node_name)
    if not isinstance(node, MutableMapping):
        return None
    return cast(MutableMapping[str, object], node)


__all__ = [
    "PromptSceneMaterializationCube",
    "PromptSceneMaterializationService",
    "PromptSceneMaterializationWorkflow",
]
