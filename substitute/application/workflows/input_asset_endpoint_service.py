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

"""Discover editable image and mask upload endpoints from live Comfy semantics."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.application.workflows.input_asset_field_policy import (
    InputAssetFieldPolicy,
)
from substitute.application.workflows.workflow_graph_topology import (
    WorkflowGraphTopology,
)
from substitute.application.workflows.workflow_node_definition_service import (
    WorkflowNodeDefinitionService,
    node_class_type,
)
from substitute.domain.workflow import (
    InputAssetEndpoint,
    InputAssetEndpointIndex,
    InputAssetRole,
)


class InputAssetEndpointService:
    """Build conservative upload endpoint indexes without owning canvas pairing."""

    def __init__(
        self,
        node_definition_service: WorkflowNodeDefinitionService | None = None,
        field_policy: InputAssetFieldPolicy | None = None,
    ) -> None:
        """Capture the shared graph-scoped live-definition authority."""

        self._node_definition_service = (
            node_definition_service or WorkflowNodeDefinitionService()
        )
        self._field_policy = field_policy or InputAssetFieldPolicy()

    def build_index(
        self,
        section_key: str,
        graph: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]] | None = None,
    ) -> InputAssetEndpointIndex:
        """Return upload endpoints classified by their actually used output types."""

        definitions = self._node_definition_service.definitions_for_graph(
            graph,
            node_definitions,
        )
        topology = WorkflowGraphTopology(graph, definitions)
        endpoints: list[InputAssetEndpoint] = []
        ambiguous_nodes: set[str] = set()
        for node_name, node in topology.nodes.items():
            class_type = node_class_type(node)
            definition = definitions.get(class_type, {})
            asset_fields = self._field_policy.fields_for_node(class_type, definition)
            if len(asset_fields) > 1:
                ambiguous_nodes.add(node_name)
                continue
            if not asset_fields:
                continue
            field = asset_fields[0]
            used_output_indexes = topology.used_output_indexes(node_name)
            used_roles = {
                role
                for output_index in used_output_indexes
                if (role := field.role_for_output_index(output_index)) is not None
            }
            role = _role_for_used_roles(used_roles)
            if role is None:
                continue
            for output_index in dict.fromkeys(
                index
                for index in used_output_indexes
                if field.role_for_output_index(index) is role
            ):
                endpoints.append(
                    InputAssetEndpoint(
                        section_key=section_key,
                        node_name=node_name,
                        field_key=field.field_key,
                        output_index=output_index,
                        role=role,
                        cardinality=field.cardinality,
                    )
                )
        return InputAssetEndpointIndex(
            endpoints=tuple(endpoints),
            ambiguous_endpoint_nodes=frozenset(ambiguous_nodes),
        )


def _role_for_used_roles(
    used_roles: set[InputAssetRole],
) -> InputAssetRole | None:
    """Apply the deliberate image-first policy for dual-used upload nodes."""

    if InputAssetRole.IMAGE in used_roles:
        return InputAssetRole.IMAGE
    if InputAssetRole.MASK in used_roles:
        return InputAssetRole.MASK
    return None


__all__ = [
    "InputAssetEndpointService",
]
