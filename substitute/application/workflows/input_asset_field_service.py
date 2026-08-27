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

"""Discover every authored input field governed by external asset transport."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
    graph_nodes,
    node_class_type,
)
from substitute.domain.workflow import InputAssetCardinality, InputAssetRole


@dataclass(frozen=True, slots=True)
class AuthoredInputAssetField:
    """Identify one authored asset field independently of graph consumption."""

    node_name: str
    field_key: str
    role: InputAssetRole
    cardinality: InputAssetCardinality


class InputAssetFieldService:
    """Project authoritative field semantics across one authored graph section."""

    def __init__(
        self,
        node_definition_service: WorkflowNodeDefinitionService | None = None,
        field_policy: InputAssetFieldPolicy | None = None,
    ) -> None:
        """Capture live-definition and input-asset semantics authorities."""

        self._node_definition_service = (
            node_definition_service or WorkflowNodeDefinitionService()
        )
        self._field_policy = field_policy or InputAssetFieldPolicy()

    def fields_for_graph(
        self,
        graph: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> tuple[AuthoredInputAssetField, ...]:
        """Return all authored asset fields without topology-based filtering."""

        definitions = self._node_definition_service.definitions_for_graph(
            graph,
            node_definitions,
        )
        fields: list[AuthoredInputAssetField] = []
        for node_name, node in graph_nodes(graph).items():
            class_type = node_class_type(node)
            definition = definitions.get(class_type, {})
            fields.extend(
                AuthoredInputAssetField(
                    node_name=node_name,
                    field_key=semantics.field_key,
                    role=semantics.preferred_role,
                    cardinality=semantics.cardinality,
                )
                for semantics in self._field_policy.fields_for_node(
                    class_type,
                    definition,
                )
            )
        return tuple(fields)


__all__ = ["AuthoredInputAssetField", "InputAssetFieldService"]
