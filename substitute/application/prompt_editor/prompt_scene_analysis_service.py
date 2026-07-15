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

"""Resolve workflow-level prompt scene authority and diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole
from substitute.domain.prompt import parse_prompt_scene_document


class PromptSceneWorkflowCube(Protocol):
    """Describe cube state required for prompt scene analysis."""

    buffer: Any


class PromptSceneWorkflow(Protocol):
    """Describe workflow state required for prompt scene analysis."""

    @property
    def stack_order(self) -> Sequence[str]:
        """Return cube aliases in workflow order."""
        ...

    @property
    def cubes(self) -> Mapping[str, PromptSceneWorkflowCube]:
        """Return cube states keyed by alias."""
        ...


@dataclass(frozen=True, slots=True)
class WorkflowScene:
    """Describe one runnable workflow scene."""

    key: str
    title: str
    order: int


@dataclass(frozen=True, slots=True)
class PromptSceneDiagnostics:
    """Describe scene issues for one prompt endpoint."""

    orphan_scene_keys: frozenset[str] = frozenset()
    duplicate_scene_keys: frozenset[str] = frozenset()

    @property
    def has_errors(self) -> bool:
        """Return whether this diagnostic contains any invalid scene markers."""

        return bool(self.orphan_scene_keys or self.duplicate_scene_keys)


@dataclass(frozen=True, slots=True)
class WorkflowSceneAnalysis:
    """Capture scene authority, runnable scenes, and prompt diagnostics."""

    authority_endpoint: PromptEndpoint | None
    scenes: tuple[WorkflowScene, ...]
    diagnostics_by_endpoint: Mapping[PromptEndpoint, PromptSceneDiagnostics]

    @property
    def can_generate_scenes(self) -> bool:
        """Return whether this workflow has an authority scene list to run."""

        return self.authority_endpoint is not None and bool(self.scenes)


class PromptSceneAnalysisService:
    """Analyze text-authored prompt scenes for one workflow."""

    def analyze(
        self,
        *,
        workflow: PromptSceneWorkflow,
        endpoint_index: PromptEndpointIndex,
    ) -> WorkflowSceneAnalysis:
        """Return scene authority, ordered runnable scenes, and diagnostics."""

        authority_endpoint = self._authority_endpoint(
            workflow=workflow,
            endpoint_index=endpoint_index,
        )
        authority_keys: frozenset[str] = frozenset()
        scenes: tuple[WorkflowScene, ...] = ()
        if authority_endpoint is not None:
            authority_document = parse_prompt_scene_document(
                _endpoint_prompt_text(workflow, authority_endpoint)
            )
            scenes = tuple(
                WorkflowScene(
                    key=scene.marker.normalized_key,
                    title=scene.marker.title,
                    order=len(
                        [
                            previous
                            for previous in authority_document.scenes[
                                : authority_document.scenes.index(scene)
                            ]
                            if not previous.marker.duplicate
                        ]
                    ),
                )
                for scene in authority_document.scenes
                if not scene.marker.duplicate
            )
            authority_keys = frozenset(scene.key for scene in scenes)

        diagnostics = {
            endpoint: self._diagnostics_for_endpoint(
                workflow=workflow,
                endpoint=endpoint,
                authority_endpoint=authority_endpoint,
                authority_scene_keys=authority_keys,
            )
            for endpoint in endpoint_index.endpoints
            if endpoint.linkable
        }
        return WorkflowSceneAnalysis(
            authority_endpoint=authority_endpoint,
            scenes=scenes,
            diagnostics_by_endpoint=diagnostics,
        )

    @staticmethod
    def _authority_endpoint(
        *,
        workflow: PromptSceneWorkflow,
        endpoint_index: PromptEndpointIndex,
    ) -> PromptEndpoint | None:
        """Return the first positive prompt endpoint in workflow stack order."""

        for cube_alias in workflow.stack_order:
            endpoint = endpoint_index.endpoint_for(cube_alias, PromptRole.POSITIVE)
            if endpoint is not None:
                return endpoint
        return None

    @staticmethod
    def _diagnostics_for_endpoint(
        *,
        workflow: PromptSceneWorkflow,
        endpoint: PromptEndpoint,
        authority_endpoint: PromptEndpoint | None,
        authority_scene_keys: frozenset[str],
    ) -> PromptSceneDiagnostics:
        """Return scene marker diagnostics for one prompt endpoint."""

        document = parse_prompt_scene_document(
            _endpoint_prompt_text(workflow, endpoint)
        )
        duplicate_keys = frozenset(
            scene.marker.normalized_key
            for scene in document.scenes
            if scene.marker.duplicate
        )
        if endpoint == authority_endpoint:
            return PromptSceneDiagnostics(duplicate_scene_keys=duplicate_keys)
        orphan_keys = frozenset(
            scene.marker.normalized_key
            for scene in document.scenes
            if scene.marker.normalized_key not in authority_scene_keys
        )
        return PromptSceneDiagnostics(
            orphan_scene_keys=orphan_keys,
            duplicate_scene_keys=duplicate_keys,
        )


def _endpoint_prompt_text(
    workflow: PromptSceneWorkflow,
    endpoint: PromptEndpoint,
) -> str:
    """Return prompt text stored at one endpoint, or an empty string if missing."""

    cube = workflow.cubes.get(endpoint.cube_alias)
    if cube is None:
        return ""
    buffer = getattr(cube, "buffer", None)
    if not isinstance(buffer, Mapping):
        return ""
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return ""
    node = nodes.get(endpoint.node_name)
    if not isinstance(node, Mapping):
        return ""
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return ""
    value = inputs.get(endpoint.field_key)
    return value if isinstance(value, str) else ""


__all__ = [
    "PromptSceneAnalysisService",
    "PromptSceneDiagnostics",
    "PromptSceneWorkflow",
    "PromptSceneWorkflowCube",
    "WorkflowScene",
    "WorkflowSceneAnalysis",
]
