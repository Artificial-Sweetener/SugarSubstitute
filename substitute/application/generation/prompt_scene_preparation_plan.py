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

"""Plan prompt scene materialization as reusable prompt-field overlays."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from substitute.application.prompt_editor import WorkflowSceneAnalysis
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.domain.prompt import (
    materialize_scene_prompt,
    parse_prompt_scene_document,
)


class PromptScenePreparationCube(Protocol):
    """Describe cube state required for prompt scene preparation."""

    buffer: Any


class PromptScenePreparationWorkflow(Protocol):
    """Describe workflow state required for prompt scene preparation."""

    @property
    def stack_order(self) -> Sequence[str]:
        """Return cube aliases in workflow order."""
        ...

    @property
    def cubes(self) -> Mapping[str, PromptScenePreparationCube]:
        """Return cube states keyed by alias."""
        ...


@dataclass(frozen=True, slots=True)
class PromptFieldIdentity:
    """Identify one prompt input field inside a workflow cube buffer."""

    cube_alias: str
    node_name: str
    field_key: str

    def as_recipe_field_key(self) -> tuple[str, str, str]:
        """Return the tuple key used by recipe serialization overlays."""

        return self.cube_alias, self.node_name, self.field_key


@dataclass(frozen=True, slots=True)
class PromptSceneFieldPlan:
    """Describe scene materialization data for one independent prompt field."""

    field: PromptFieldIdentity
    original_text: str
    universal_text: str
    scene_text_by_key: Mapping[str, str]

    def materialized_text_for_scene(self, scene_key: str) -> str:
        """Return universal text plus this field's matching scene block."""

        return materialize_scene_prompt(
            universal_text=self.universal_text,
            scene_text=self.scene_text_by_key.get(scene_key, ""),
        )


@dataclass(frozen=True, slots=True)
class PromptScenePreparationPlan:
    """Render scene-specific prompt replacements without reparsing prompt text."""

    scene_keys: frozenset[str]
    fields: tuple[PromptSceneFieldPlan, ...]

    def prompt_field_overrides_for_scene(
        self,
        scene_key: str,
    ) -> dict[tuple[str, str, str], str]:
        """Return prompt-field override text for one known scene key."""

        if scene_key not in self.scene_keys:
            raise ValueError(f"Unknown workflow scene key: {scene_key}")
        return {
            field_plan.field.as_recipe_field_key(): (
                field_plan.materialized_text_for_scene(scene_key)
            )
            for field_plan in self.fields
        }


class PromptScenePreparationPlanBuilder:
    """Build reusable prompt-scene overlay plans for one workflow snapshot."""

    def build(
        self,
        *,
        workflow: PromptScenePreparationWorkflow,
        workflow_id: str,
        endpoint_index: PromptEndpointIndex,
        scene_analysis: WorkflowSceneAnalysis,
    ) -> PromptScenePreparationPlan:
        """Parse independent prompt endpoints once and return an overlay plan."""

        _ = workflow_id
        scene_keys = frozenset(scene.key for scene in scene_analysis.scenes)
        fields: list[PromptSceneFieldPlan] = []
        for endpoint in endpoint_index.endpoints:
            if not endpoint.linkable:
                continue
            if _endpoint_has_active_prompt_link(workflow, endpoint):
                continue
            current_text = _endpoint_prompt_text(workflow, endpoint)
            document = parse_prompt_scene_document(current_text)
            scene_text_by_key: dict[str, str] = {}
            for scene in document.scenes:
                if scene.marker.duplicate:
                    continue
                scene_text_by_key.setdefault(scene.marker.normalized_key, scene.text)
            fields.append(
                PromptSceneFieldPlan(
                    field=PromptFieldIdentity(
                        cube_alias=endpoint.cube_alias,
                        node_name=endpoint.node_name,
                        field_key=endpoint.field_key,
                    ),
                    original_text=current_text,
                    universal_text=document.universal_text,
                    scene_text_by_key=scene_text_by_key,
                )
            )
        return PromptScenePreparationPlan(
            scene_keys=scene_keys,
            fields=tuple(fields),
        )


def _endpoint_prompt_text(
    workflow: PromptScenePreparationWorkflow,
    endpoint: PromptEndpoint,
) -> str:
    """Return prompt text stored at one endpoint, or an empty string if missing."""

    node = _endpoint_node(workflow, endpoint)
    if node is None:
        return ""
    inputs = node.get("inputs")
    if not isinstance(inputs, Mapping):
        return ""
    value = inputs.get(endpoint.field_key)
    return value if isinstance(value, str) else ""


def _endpoint_has_active_prompt_link(
    workflow: PromptScenePreparationWorkflow,
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
    workflow: PromptScenePreparationWorkflow,
    endpoint: PromptEndpoint,
) -> Mapping[str, object] | None:
    """Return node payload for one endpoint when available."""

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
    if not isinstance(node, Mapping):
        return None
    return node


__all__ = [
    "PromptFieldIdentity",
    "PromptSceneFieldPlan",
    "PromptScenePreparationCube",
    "PromptScenePreparationPlan",
    "PromptScenePreparationPlanBuilder",
    "PromptScenePreparationWorkflow",
]
