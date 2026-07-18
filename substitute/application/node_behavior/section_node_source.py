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

"""Prepare definition-hydrated node metadata for one behavior snapshot pass."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping

from substitute.application.ports import NodeDefinitionGateway
from substitute.domain.cubes import SubgraphWrapperDefinitionIndex
from substitute.shared.logging.logger import get_logger, log_timing

from .editor_definition_resolver import EditorNodeDefinitionResolver
from .list_value_resolver import extract_live_list_options
from .node_card_order import wired_node_order

_LOGGER = get_logger("application.node_behavior.section_node_source")


@dataclass(frozen=True, slots=True)
class SectionNodeSource:
    """Describe one node after metadata preparation and before behavior resolution."""

    node_name: str
    class_type: str
    node_data: Mapping[str, object]
    node_title: str | None
    node_definition: Mapping[str, object] | None
    input_keys: tuple[str, ...]


class SectionNodeSourceFactory:
    """Hydrate and normalize all node sources within one isolated section."""

    def __init__(self, node_definition_gateway: NodeDefinitionGateway) -> None:
        """Store the shared editor-definition authority."""

        self._definition_resolver = EditorNodeDefinitionResolver(
            node_definition_gateway
        )

    def prepare(
        self,
        *,
        alias: str,
        buffer: Mapping[str, object],
    ) -> tuple[SectionNodeSource, ...]:
        """Return ordered node metadata hydrated exactly once for the section."""

        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return ()
        layout_nodes = _layout_nodes(buffer)
        wrapper_definitions = SubgraphWrapperDefinitionIndex.from_runtime_graph(buffer)
        sources: list[SectionNodeSource] = []
        for node_name in wired_node_order(nodes):
            node_data = nodes.get(node_name)
            if not isinstance(node_data, Mapping):
                continue
            class_type = node_data.get("class_type")
            if not isinstance(class_type, str):
                continue
            node_definition = self._lookup_node_definition(
                class_type=class_type,
                node_data=node_data,
                wrapper_definitions=wrapper_definitions,
                cube_alias=alias,
                node_name=node_name,
            )
            wrapper_title = wrapper_definitions.display_name_for_class_type(class_type)
            node_title = (
                _node_title(
                    node_name=node_name,
                    node_data=node_data,
                    layout_nodes=layout_nodes,
                )
                or wrapper_title
            )
            sources.append(
                SectionNodeSource(
                    node_name=node_name,
                    class_type=class_type,
                    node_data=node_data,
                    node_title=node_title,
                    node_definition=node_definition,
                    input_keys=tuple(
                        _ordered_input_keys(
                            node_inputs=node_data.get("inputs", {}),
                            resolved_definition=node_definition,
                        )
                    ),
                )
            )
        return tuple(sources)

    def _lookup_node_definition(
        self,
        *,
        class_type: str,
        node_data: Mapping[str, object],
        wrapper_definitions: SubgraphWrapperDefinitionIndex,
        cube_alias: str,
        node_name: str,
    ) -> Mapping[str, object] | None:
        """Return runtime metadata through the editor definition authority."""

        lookup_started_at = perf_counter()
        resolved_definition = self._definition_resolver.resolve(
            class_type=class_type,
            node_data=node_data,
            wrapper_definitions=wrapper_definitions,
            cube_alias=cube_alias,
            node_name=node_name,
        )
        available = isinstance(resolved_definition, Mapping)
        log_timing(
            _LOGGER,
            "Resolved node definition for section source",
            started_at=lookup_started_at,
            level="debug",
            class_type=class_type,
            definition_available=available,
        )
        return resolved_definition if available else None


def is_subgraph_wrapper_definition(
    resolved_definition: Mapping[str, object] | None,
) -> bool:
    """Return whether a definition describes a wrapper surface node."""

    return bool(
        isinstance(resolved_definition, Mapping)
        and resolved_definition.get("subgraph_wrapper") is True
    )


def _ordered_input_keys(
    *,
    node_inputs: object,
    resolved_definition: Mapping[str, object] | None,
) -> list[str]:
    """Return definition-owned field order plus persisted extras."""

    present = list(node_inputs.keys()) if isinstance(node_inputs, Mapping) else []
    definition_input = (
        resolved_definition.get("input", {})
        if isinstance(resolved_definition, Mapping)
        else {}
    )
    definition_keys: list[str] = []
    definition_fields: dict[str, object] = {}
    if isinstance(definition_input, Mapping):
        for section_name in ("required", "optional"):
            section = definition_input.get(section_name, {})
            if isinstance(section, Mapping):
                definition_fields.update(
                    (key, value)
                    for key, value in section.items()
                    if isinstance(key, str)
                )
                definition_keys.extend(
                    key for key in section.keys() if isinstance(key, str)
                )
    ordered: list[str] = []
    if is_subgraph_wrapper_definition(resolved_definition):
        for key in definition_keys:
            if (
                key in present
                or _definition_field_renders_without_input(definition_fields.get(key))
            ) and key not in ordered:
                ordered.append(key)
        ordered.extend(
            key for key in present if isinstance(key, str) and key not in ordered
        )
        return ordered
    ordered.extend(key for key in definition_keys if key not in ordered)
    ordered.extend(
        key for key in present if isinstance(key, str) and key not in ordered
    )
    return ordered


def _definition_field_renders_without_input(field_definition: object) -> bool:
    """Return whether a wrapper field is renderable without authored input."""

    if (
        not isinstance(field_definition, list)
        or len(field_definition) < 2
        or not isinstance(field_definition[1], Mapping)
    ):
        return False
    return "default" in field_definition[1] or bool(
        extract_live_list_options(field_definition)
    )


def _layout_nodes(buffer: Mapping[str, object]) -> Mapping[str, object]:
    """Return cube layout node metadata when present."""

    layout = buffer.get("layout")
    if not isinstance(layout, Mapping):
        return {}
    layout_nodes = layout.get("nodes")
    return layout_nodes if isinstance(layout_nodes, Mapping) else {}


def _node_title(
    *,
    node_name: str,
    node_data: object,
    layout_nodes: Mapping[str, object],
) -> str | None:
    """Return the author-facing node title retained for behavior inference."""

    layout_node = layout_nodes.get(node_name)
    if isinstance(layout_node, Mapping):
        layout_title = layout_node.get("title")
        if isinstance(layout_title, str):
            return layout_title
    if isinstance(node_data, Mapping):
        meta = node_data.get("_meta")
        if isinstance(meta, Mapping):
            meta_title = meta.get("title")
            if isinstance(meta_title, str):
                return meta_title
    if node_name in {"positive_prompt", "negative_prompt"}:
        return node_name
    return None


__all__ = [
    "SectionNodeSource",
    "SectionNodeSourceFactory",
    "is_subgraph_wrapper_definition",
]
