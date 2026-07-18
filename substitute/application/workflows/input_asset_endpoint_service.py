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

_IMAGE_TYPE = "IMAGE"
_MASK_TYPE = "MASK"
_LEGACY_UPLOAD_FIELDS: dict[str, str] = {
    "LoadImage": "image",
    "LoadImageMask": "image",
}
_LEGACY_OUTPUT_TYPES: dict[str, tuple[str, ...]] = {
    "LoadImage": (_IMAGE_TYPE, _MASK_TYPE),
    "LoadImageMask": (_MASK_TYPE,),
}


class InputAssetEndpointService:
    """Build conservative upload endpoint indexes without owning canvas pairing."""

    def __init__(
        self,
        node_definition_service: WorkflowNodeDefinitionService | None = None,
    ) -> None:
        """Capture the shared graph-scoped live-definition authority."""

        self._node_definition_service = (
            node_definition_service or WorkflowNodeDefinitionService()
        )

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
            upload_fields = _upload_fields(class_type, definition)
            if len(upload_fields) > 1:
                ambiguous_nodes.add(node_name)
                continue
            if not upload_fields:
                continue
            output_types = _output_types(class_type, definition)
            used_output_indexes = tuple(
                edge.output_index
                for edge in topology.outgoing_edges(node_name)
                if 0 <= edge.output_index < len(output_types)
                and output_types[edge.output_index] in {_IMAGE_TYPE, _MASK_TYPE}
            )
            used_types = {output_types[index] for index in used_output_indexes}
            role = _role_for_used_types(used_types)
            if role is None:
                continue
            selected_type = _IMAGE_TYPE if role is InputAssetRole.IMAGE else _MASK_TYPE
            for output_index in dict.fromkeys(
                index
                for index in used_output_indexes
                if output_types[index] == selected_type
            ):
                endpoints.append(
                    InputAssetEndpoint(
                        section_key=section_key,
                        node_name=node_name,
                        field_key=upload_fields[0],
                        output_index=output_index,
                        role=role,
                    )
                )
        return InputAssetEndpointIndex(
            endpoints=tuple(endpoints),
            ambiguous_endpoint_nodes=frozenset(ambiguous_nodes),
        )


def field_metadata(field_info: object) -> Mapping[str, object]:
    """Return the metadata mapping from one normalized Comfy widget definition."""

    if isinstance(field_info, (list, tuple)) and len(field_info) > 1:
        metadata = field_info[1]
        if isinstance(metadata, Mapping):
            return metadata
    return {}


def declared_input_type(
    definition: Mapping[str, object],
    field_key: str,
) -> str | None:
    """Return one normalized declared input socket type when available."""

    input_groups = definition.get("input", {})
    if not isinstance(input_groups, Mapping):
        return None
    for group_name in ("required", "optional"):
        group = input_groups.get(group_name, {})
        if not isinstance(group, Mapping):
            continue
        field_info = group.get(field_key)
        if not isinstance(field_info, (list, tuple)) or not field_info:
            continue
        declared = field_info[0]
        return declared.upper() if isinstance(declared, str) else None
    return None


def _upload_fields(
    class_type: str,
    definition: Mapping[str, object],
) -> tuple[str, ...]:
    """Return trustworthy input-folder image upload widget fields."""

    input_groups = definition.get("input", {})
    discovered: list[str] = []
    if isinstance(input_groups, Mapping):
        for group_name in ("required", "optional"):
            group = input_groups.get(group_name, {})
            if not isinstance(group, Mapping):
                continue
            for field_key, field_info in group.items():
                metadata = field_metadata(field_info)
                folder = metadata.get("image_folder")
                if metadata.get("image_upload") is True and folder in {None, "input"}:
                    discovered.append(str(field_key))
    if not discovered and class_type in _LEGACY_UPLOAD_FIELDS:
        discovered.append(_LEGACY_UPLOAD_FIELDS[class_type])
    return tuple(dict.fromkeys(discovered))


def _output_types(
    class_type: str,
    definition: Mapping[str, object],
) -> tuple[str, ...]:
    """Return exact live output socket types or conservative built-in fallbacks."""

    output = definition.get("output")
    if isinstance(output, (list, tuple)):
        return tuple(str(value).upper() for value in output)
    return _LEGACY_OUTPUT_TYPES.get(class_type, ())


def _role_for_used_types(used_types: set[str]) -> InputAssetRole | None:
    """Apply the deliberate image-first policy for dual-used upload nodes."""

    if _IMAGE_TYPE in used_types:
        return InputAssetRole.IMAGE
    if _MASK_TYPE in used_types:
        return InputAssetRole.MASK
    return None


__all__ = [
    "InputAssetEndpointService",
    "declared_input_type",
    "field_metadata",
]
