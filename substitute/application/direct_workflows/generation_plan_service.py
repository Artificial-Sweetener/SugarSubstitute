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

"""Build immutable direct-workflow generation plans from document state."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.ports import NodeDefinitionGateway, NodeDefinitionHydrator
from substitute.domain.comfy_workflow import (
    ComfyApiGraphBuildError,
    ComfyApiGraphBuilder,
    DirectWorkflowState,
)
from substitute.domain.comfy_workflow.editor_definitions import (
    workflow_node_execution_role,
)
from substitute.domain.comfy_workflow.node_roles import WorkflowNodeExecutionRole
from substitute.domain.comfy_workflow.output_manifest import (
    ComfyImageOutputDiscovery,
    DirectWorkflowGenerationPlan,
)


class DirectWorkflowGenerationPlanService:
    """Coordinate direct graph lowering, validation, and output discovery."""

    def __init__(
        self,
        builder: ComfyApiGraphBuilder | None = None,
        *,
        output_discovery: ComfyImageOutputDiscovery | None = None,
        node_definition_hydrator: NodeDefinitionHydrator | None = None,
        node_definition_gateway: NodeDefinitionGateway | None = None,
    ) -> None:
        """Store focused graph-planning collaborators."""

        self._builder = builder or ComfyApiGraphBuilder()
        self._output_discovery = output_discovery or ComfyImageOutputDiscovery()
        self._node_definition_hydrator = node_definition_hydrator
        self._node_definition_gateway = node_definition_gateway

    def build(self, document: DirectWorkflowState) -> DirectWorkflowGenerationPlan:
        """Return an authored graph and immutable image-output manifest."""

        buffer = document.buffer
        if not isinstance(buffer, Mapping):
            raise ValueError("Direct Comfy workflow has no editable graph buffer.")
        node_classes = _active_executable_node_classes(buffer)
        self._validate_active_node_classes(node_classes)
        graph = self._builder.build(buffer)
        definitions = self._load_node_definitions(node_classes)
        return DirectWorkflowGenerationPlan(
            authored_api_graph=graph,
            output_manifest=self._output_discovery.discover(
                graph,
                node_definitions=definitions,
            ),
        )

    def _validate_active_node_classes(self, node_classes: tuple[str, ...]) -> None:
        """Fail before lowering when active backend classes are unavailable."""

        hydrator = self._node_definition_hydrator
        if hydrator is None:
            return
        result = hydrator.ensure_node_definitions(node_classes)
        if result.unavailable:
            raise ComfyApiGraphBuildError(
                "Comfy does not provide active workflow node classes: "
                + ", ".join(result.unavailable)
            )

    def _load_node_definitions(
        self,
        node_classes: tuple[str, ...],
    ) -> dict[str, Mapping[str, object]]:
        """Return normalized live definitions used for output classification."""

        gateway = self._node_definition_gateway
        if gateway is None:
            return {}
        definitions: dict[str, Mapping[str, object]] = {}
        for node_class in node_classes:
            payload = gateway.get_node_definition(node_class)
            definition = payload.get(node_class)
            if not isinstance(definition, Mapping):
                payload = gateway.get_required_node_definition(node_class)
                definition = payload.get(node_class)
            if not isinstance(definition, Mapping):
                raise ComfyApiGraphBuildError(
                    "Comfy did not return required live metadata for active workflow "
                    f"node class {node_class!r}."
                )
            definitions[node_class] = definition
        return definitions


def _active_executable_node_classes(
    buffer: Mapping[str, object],
) -> tuple[str, ...]:
    """Return active backend classes that the API graph will emit."""

    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return ()
    classes: set[str] = set()
    for node in nodes.values():
        if not isinstance(node, Mapping):
            continue
        if workflow_node_execution_role(node) != WorkflowNodeExecutionRole.EXECUTABLE:
            continue
        if node.get("mode", 0) in {2, 4}:
            continue
        class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type.strip():
            classes.add(class_type.strip())
    return tuple(sorted(classes))


__all__ = ["DirectWorkflowGenerationPlanService"]
