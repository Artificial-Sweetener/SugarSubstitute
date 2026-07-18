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

"""Collect live node-definition classes needed before editor projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.domain.cubes import (
    SubgraphWrapperDefinitionIndex,
    is_subgraph_wrapper_class_type,
)
from substitute.domain.comfy_workflow.editor_definitions import (
    workflow_local_editor_definition,
    workflow_node_execution_role,
)
from substitute.domain.comfy_workflow.node_roles import WorkflowNodeExecutionRole


@dataclass(frozen=True, slots=True)
class NodeDefinitionRequirement:
    """Identify one live Comfy definition required for editor projection."""

    class_type: str
    cube_alias: str
    node_name: str
    source: str
    live_required: bool = True


def required_node_definition_classes_for_editor_projection(
    buffers: Mapping[str, Mapping[str, object]],
) -> tuple[str, ...]:
    """Return live node classes needed before editor projection builds widgets.

    Editor projection requires live metadata for visible top-level nodes and for
    hidden body nodes that back public wrapper fields. Other hidden subgraph
    implementation nodes are execution details, not editor control definitions.
    """

    requirements = required_node_definition_requirements_for_editor_projection(buffers)
    return tuple(sorted({requirement.class_type for requirement in requirements}))


def required_node_definition_requirements_for_editor_projection(
    buffers: Mapping[str, Mapping[str, object]],
) -> tuple[NodeDefinitionRequirement, ...]:
    """Return cube-owned live definition requirements for editor projection."""

    requirements: set[NodeDefinitionRequirement] = set()
    for cube_alias, buffer in buffers.items():
        if not isinstance(buffer, Mapping):
            continue
        wrapper_definitions = SubgraphWrapperDefinitionIndex.from_runtime_graph(buffer)
        requirements.update(
            _node_requirements_from_mapping(
                buffer.get("nodes"),
                cube_alias=cube_alias,
                wrapper_definitions=wrapper_definitions,
            )
        )
    return tuple(
        sorted(
            requirements,
            key=lambda requirement: (
                requirement.class_type,
                requirement.cube_alias,
                requirement.node_name,
                requirement.source,
            ),
        )
    )


def _node_requirements_from_mapping(
    nodes: object,
    *,
    cube_alias: str,
    wrapper_definitions: SubgraphWrapperDefinitionIndex,
) -> set[NodeDefinitionRequirement]:
    """Return projection requirements from one serialized node mapping."""

    requirements: set[NodeDefinitionRequirement] = set()
    if not isinstance(nodes, Mapping):
        return requirements
    for node_name, node_data in nodes.items():
        node_class = _node_class_from_payload(node_data)
        if node_class is not None:
            if is_subgraph_wrapper_class_type(node_class):
                for body_class in _concrete_wrapper_body_classes(
                    node_class,
                    wrapper_definitions=wrapper_definitions,
                ):
                    requirements.add(
                        NodeDefinitionRequirement(
                            class_type=body_class,
                            cube_alias=cube_alias,
                            node_name=str(node_name),
                            source="wrapper_body",
                        )
                    )
                continue
            if not isinstance(node_data, Mapping):
                continue
            if (
                workflow_node_execution_role(node_data)
                != WorkflowNodeExecutionRole.EXECUTABLE.value
            ):
                continue
            requirements.add(
                NodeDefinitionRequirement(
                    class_type=node_class,
                    cube_alias=cube_alias,
                    node_name=str(node_name),
                    source="top_level",
                    live_required=(workflow_local_editor_definition(node_data) is None),
                )
            )
    return requirements


def _concrete_wrapper_body_classes(
    class_type: str,
    *,
    wrapper_definitions: SubgraphWrapperDefinitionIndex,
    seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Return non-wrapper body classes reachable from one wrapper class."""

    if class_type in seen:
        return ()
    next_seen = frozenset((*seen, class_type))
    body_classes: set[str] = set()
    for body_class in wrapper_definitions.body_node_classes_for_class_type(class_type):
        if is_subgraph_wrapper_class_type(body_class):
            body_classes.update(
                _concrete_wrapper_body_classes(
                    body_class,
                    wrapper_definitions=wrapper_definitions,
                    seen=next_seen,
                )
            )
            continue
        body_classes.add(body_class)
    return tuple(sorted(body_classes))


def _node_class_from_payload(node_data: object) -> str | None:
    """Return a normalized node class from one serialized node payload."""

    if not isinstance(node_data, Mapping):
        return None
    for key in ("class_type", "type"):
        value = node_data.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


__all__ = [
    "NodeDefinitionRequirement",
    "required_node_definition_classes_for_editor_projection",
    "required_node_definition_requirements_for_editor_projection",
]
