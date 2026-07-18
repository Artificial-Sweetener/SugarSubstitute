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

"""Discover authored image-output sinks in executable Comfy graphs."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from substitute.domain.common import JsonObject


@dataclass(frozen=True, slots=True, order=True)
class ComfyOutputSocket:
    """Identify one typed output socket in a Comfy API graph."""

    node_id: str
    output_index: int


@dataclass(frozen=True, slots=True)
class AuthoredImageSink:
    """Describe one authored terminal output declaration for an image socket."""

    node_id: str
    input_name: str
    title: str


@dataclass(frozen=True, slots=True)
class DirectImageOutputSource:
    """Group authored image sinks that consume the same upstream socket."""

    socket: ComfyOutputSocket
    sinks: tuple[AuthoredImageSink, ...]
    source_key: str
    label: str
    order: int


@dataclass(frozen=True, slots=True)
class DirectWorkflowOutputManifest:
    """Describe image takeover sources and preserved output-node targets."""

    sources: tuple[DirectImageOutputSource, ...]
    hijacked_sink_node_ids: frozenset[str]
    preserved_output_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DirectWorkflowGenerationPlan:
    """Keep an authored API graph together with immutable output intent."""

    authored_api_graph: JsonObject
    output_manifest: DirectWorkflowOutputManifest


class ComfyImageOutputDiscovery:
    """Find safely replaceable terminal image sinks using live definitions."""

    def discover(
        self,
        graph: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]],
    ) -> DirectWorkflowOutputManifest:
        """Return deduplicated image sources and untouched output targets."""

        downstream_node_ids = _linked_source_node_ids(graph)
        grouped_sinks: OrderedDict[ComfyOutputSocket, list[AuthoredImageSink]] = (
            OrderedDict()
        )
        all_output_node_ids: list[str] = []
        hijacked_node_ids: set[str] = set()

        for raw_node_id, raw_node in graph.items():
            node_id = str(raw_node_id)
            if not isinstance(raw_node, Mapping):
                continue
            definition = _definition_for_node(raw_node, node_definitions)
            if not _is_output_node(definition):
                continue
            all_output_node_ids.append(node_id)
            if node_id in downstream_node_ids:
                continue
            image_inputs = _connected_image_inputs(raw_node, definition)
            if not image_inputs:
                continue
            hijacked_node_ids.add(node_id)
            title = _node_title(raw_node, fallback=node_id)
            for input_name, socket in image_inputs:
                grouped_sinks.setdefault(socket, []).append(
                    AuthoredImageSink(
                        node_id=node_id,
                        input_name=input_name,
                        title=title,
                    )
                )

        sources = tuple(
            DirectImageOutputSource(
                socket=socket,
                sinks=tuple(sinks),
                source_key=f"direct:{socket.node_id}:{socket.output_index}",
                label=str(order + 1),
                order=order,
            )
            for order, (socket, sinks) in enumerate(grouped_sinks.items())
        )
        return DirectWorkflowOutputManifest(
            sources=sources,
            hijacked_sink_node_ids=frozenset(hijacked_node_ids),
            preserved_output_node_ids=tuple(
                node_id
                for node_id in all_output_node_ids
                if node_id not in hijacked_node_ids
            ),
        )


def is_terminal_image_output_sink(
    *,
    node_id: str,
    node: Mapping[str, object],
    graph: Mapping[str, object],
    node_definition: Mapping[str, object] | None,
) -> bool:
    """Return whether one node is a safely replaceable image-output sink."""

    return bool(
        _is_output_node(node_definition)
        and str(node_id) not in _linked_source_node_ids(graph)
        and _connected_image_inputs(node, node_definition)
    )


def _definition_for_node(
    node: Mapping[str, object],
    definitions: Mapping[str, Mapping[str, object]],
) -> Mapping[str, object] | None:
    """Return the live definition matching one graph node class."""

    class_type = node.get("class_type")
    if not isinstance(class_type, str):
        return None
    return definitions.get(class_type)


def _is_output_node(definition: Mapping[str, object] | None) -> bool:
    """Return whether live Comfy metadata declares an execution output."""

    return isinstance(definition, Mapping) and definition.get("output_node") is True


def _connected_image_inputs(
    node: Mapping[str, object],
    definition: Mapping[str, object] | None,
) -> tuple[tuple[str, ComfyOutputSocket], ...]:
    """Return connected canonical IMAGE inputs in definition order."""

    if not isinstance(definition, Mapping):
        return ()
    node_inputs = node.get("inputs")
    definition_input = definition.get("input")
    if not isinstance(node_inputs, Mapping) or not isinstance(
        definition_input, Mapping
    ):
        return ()
    connected: list[tuple[str, ComfyOutputSocket]] = []
    for section_name in ("required", "optional"):
        section = definition_input.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for raw_name, field_definition in section.items():
            input_name = str(raw_name)
            if not _is_canonical_image_field(field_definition):
                continue
            socket = _linked_output_socket(node_inputs.get(input_name))
            if socket is not None:
                connected.append((input_name, socket))
    return tuple(connected)


def _is_canonical_image_field(field_definition: object) -> bool:
    """Return whether a Comfy input definition declares canonical IMAGE data."""

    return bool(
        isinstance(field_definition, Sequence)
        and not isinstance(field_definition, str | bytes)
        and field_definition
        and field_definition[0] == "IMAGE"
    )


def _linked_output_socket(value: object) -> ComfyOutputSocket | None:
    """Parse one canonical Comfy API link into a typed socket identity."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, str | bytes)
        or len(value) < 2
        or not isinstance(value[0], str | int)
        or isinstance(value[1], bool)
        or not isinstance(value[1], int)
        or value[1] < 0
    ):
        return None
    return ComfyOutputSocket(str(value[0]), value[1])


def _linked_source_node_ids(graph: Mapping[str, object]) -> frozenset[str]:
    """Return node IDs referenced by any downstream graph input."""

    linked: set[str] = set()
    for raw_node in graph.values():
        if not isinstance(raw_node, Mapping):
            continue
        inputs = raw_node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for value in inputs.values():
            socket = _linked_output_socket(value)
            if socket is not None:
                linked.add(socket.node_id)
    return frozenset(linked)


def _node_title(node: Mapping[str, object], *, fallback: str) -> str:
    """Return an authored node title for diagnostics."""

    metadata = node.get("_meta")
    if isinstance(metadata, Mapping):
        title = metadata.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return fallback


__all__ = [
    "AuthoredImageSink",
    "ComfyImageOutputDiscovery",
    "ComfyOutputSocket",
    "DirectImageOutputSource",
    "DirectWorkflowGenerationPlan",
    "DirectWorkflowOutputManifest",
    "is_terminal_image_output_sink",
]
