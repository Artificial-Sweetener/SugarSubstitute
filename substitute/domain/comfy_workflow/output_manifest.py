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

"""Discover authored visual-output sinks in executable Comfy graphs."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from substitute.domain.common import JsonObject
from substitute.domain.output_media import OutputMediaKind

_IMAGE_RECOVERY_MEDIA_KIND = OutputMediaKind.IMAGE
_VIDEO_SINK_CLASSES = frozenset(
    {"PreviewVideo", "SaveVideo", "SaveWEBM", "VHS_VideoCombine"}
)


@dataclass(frozen=True, slots=True, order=True)
class ComfyOutputSocket:
    """Identify one typed output socket in a Comfy API graph."""

    node_id: str
    output_index: int


@dataclass(frozen=True, slots=True)
class AuthoredOutputSink:
    """Describe one authored terminal visual-output declaration."""

    node_id: str
    input_name: str
    title: str
    media_kind: OutputMediaKind


@dataclass(frozen=True, slots=True)
class DirectOutputSource:
    """Group authored sinks represented by one output navigation source."""

    socket: ComfyOutputSocket
    sinks: tuple[AuthoredOutputSink, ...]
    source_key: str
    label: str
    order: int
    media_kind: OutputMediaKind

    @property
    def requires_image_recovery(self) -> bool:
        """Return whether execution needs a temporary PreviewImage target."""

        return self.media_kind is _IMAGE_RECOVERY_MEDIA_KIND

    @property
    def output_node_id(self) -> str:
        """Return the authored node that emits non-recovered media."""

        return self.sinks[0].node_id


@dataclass(frozen=True, slots=True)
class DirectWorkflowOutputManifest:
    """Describe visual-output sources and preserved execution targets."""

    sources: tuple[DirectOutputSource, ...]
    hijacked_sink_node_ids: frozenset[str]
    preserved_output_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DirectWorkflowGenerationPlan:
    """Keep an authored API graph together with immutable output intent."""

    authored_api_graph: JsonObject
    output_manifest: DirectWorkflowOutputManifest


class ComfyOutputDiscovery:
    """Find terminal image and video sinks using live definitions."""

    def discover(
        self,
        graph: Mapping[str, object],
        *,
        node_definitions: Mapping[str, Mapping[str, object]],
    ) -> DirectWorkflowOutputManifest:
        """Return typed visual sources and untouched output targets."""

        downstream_node_ids = _linked_source_node_ids(graph)
        grouped_images: OrderedDict[ComfyOutputSocket, list[AuthoredOutputSink]] = (
            OrderedDict()
        )
        video_sources: list[tuple[ComfyOutputSocket, AuthoredOutputSink]] = []
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
            media_inputs = _connected_media_inputs(raw_node, definition)
            if not media_inputs:
                continue
            title = _node_title(raw_node, fallback=node_id)
            for input_name, socket, media_kind in media_inputs:
                sink = AuthoredOutputSink(
                    node_id=node_id,
                    input_name=input_name,
                    title=title,
                    media_kind=media_kind,
                )
                if media_kind is OutputMediaKind.IMAGE:
                    hijacked_node_ids.add(node_id)
                    grouped_images.setdefault(socket, []).append(sink)
                else:
                    video_sources.append((socket, sink))

        unordered_sources = [
            DirectOutputSource(
                socket=socket,
                sinks=tuple(sinks),
                source_key=f"direct:{socket.node_id}:{socket.output_index}",
                label="",
                order=0,
                media_kind=OutputMediaKind.IMAGE,
            )
            for socket, sinks in grouped_images.items()
        ]
        unordered_sources.extend(
            DirectOutputSource(
                socket=socket,
                sinks=(sink,),
                source_key=f"direct:{sink.node_id}",
                label="",
                order=0,
                media_kind=OutputMediaKind.VIDEO,
            )
            for socket, sink in video_sources
        )
        source_order = {str(node_id): index for index, node_id in enumerate(graph)}
        ordered_sources = sorted(
            unordered_sources,
            key=lambda source: min(
                source_order.get(sink.node_id, len(source_order))
                for sink in source.sinks
            ),
        )
        sources = tuple(
            DirectOutputSource(
                socket=source.socket,
                sinks=source.sinks,
                source_key=source.source_key,
                label=str(order + 1),
                order=order,
                media_kind=source.media_kind,
            )
            for order, source in enumerate(ordered_sources)
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


def is_terminal_output_sink(
    *,
    node_id: str,
    node: Mapping[str, object],
    graph: Mapping[str, object],
    node_definition: Mapping[str, object] | None,
) -> bool:
    """Return whether one node is a terminal supported visual-output sink."""

    return bool(
        _is_output_node(node_definition)
        and str(node_id) not in _linked_source_node_ids(graph)
        and _connected_media_inputs(node, node_definition)
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


def _connected_media_inputs(
    node: Mapping[str, object],
    definition: Mapping[str, object] | None,
) -> tuple[tuple[str, ComfyOutputSocket, OutputMediaKind], ...]:
    """Return connected visual inputs in live-definition order."""

    if not isinstance(definition, Mapping):
        return ()
    node_inputs = node.get("inputs")
    definition_input = definition.get("input")
    if not isinstance(node_inputs, Mapping) or not isinstance(
        definition_input, Mapping
    ):
        return ()
    class_type = node.get("class_type")
    connected: list[tuple[str, ComfyOutputSocket, OutputMediaKind]] = []
    for section_name in ("required", "optional"):
        section = definition_input.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for raw_name, field_definition in section.items():
            input_name = str(raw_name)
            media_kind = _field_media_kind(
                field_definition,
                class_type=class_type if isinstance(class_type, str) else "",
            )
            if media_kind is None:
                continue
            socket = _linked_output_socket(node_inputs.get(input_name))
            if socket is not None:
                connected.append((input_name, socket, media_kind))
    return tuple(connected)


def _field_media_kind(
    field_definition: object,
    *,
    class_type: str,
) -> OutputMediaKind | None:
    """Classify one live input definition, including known video adapters."""

    if (
        not isinstance(field_definition, Sequence)
        or isinstance(field_definition, str | bytes)
        or not field_definition
    ):
        return None
    declared_type = field_definition[0]
    if declared_type == "VIDEO":
        return OutputMediaKind.VIDEO
    if declared_type == "IMAGE":
        return (
            OutputMediaKind.VIDEO
            if class_type in _VIDEO_SINK_CLASSES
            else OutputMediaKind.IMAGE
        )
    return None


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
    "AuthoredOutputSink",
    "ComfyOutputDiscovery",
    "ComfyOutputSocket",
    "DirectOutputSource",
    "DirectWorkflowGenerationPlan",
    "DirectWorkflowOutputManifest",
    "is_terminal_output_sink",
]
