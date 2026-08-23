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

"""Whole-node link-group fixtures."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Mapping, cast

from substitute.application.workflows import NodeLinkGroupService
from substitute.domain.links import NodeLinkEndpoint, NodeLinkEndpointIndex


class _NodeLinkEndpointProvider:
    """Build node-link endpoints for minimal service-test buffers."""

    _prompt_reset = {"value": ""}
    _vectorscope_keys = (
        "alt",
        "brightness",
        "contrast",
        "saturation",
        "r",
        "g",
        "b",
        "method",
        "scaling",
    )

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, object],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return test endpoints for prompt and VectorscopeCC nodes."""

        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            cube_state = cube_states.get(cube_alias)
            buffer = getattr(cube_state, "buffer", {})
            nodes = buffer.get("nodes", {}) if isinstance(buffer, dict) else {}
            if not isinstance(nodes, Mapping):
                continue
            prompt_node = nodes.get("positive_prompt")
            if isinstance(prompt_node, Mapping):
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name="positive_prompt",
                        class_type=str(prompt_node.get("class_type", "String")),
                        family="prompt:positive",
                        editable_value_keys=("value",),
                        reset_values=self._prompt_reset,
                    )
                )
            vectorscope_node = nodes.get("vectorscopecc")
            if isinstance(vectorscope_node, Mapping):
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name="vectorscopecc",
                        class_type=str(vectorscope_node.get("class_type", "")),
                        family="vectorscopecc",
                        editable_value_keys=self._vectorscope_keys,
                        graph_signature=self._graph_signature(vectorscope_node),
                    )
                )
        return NodeLinkEndpointIndex.from_endpoints(endpoints)

    @staticmethod
    def _graph_signature(
        node: Mapping[str, object],
    ) -> tuple[tuple[str, object], ...]:
        """Return a compact graph signature for connection-shaped test inputs."""

        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            return ()
        signature: list[tuple[str, object]] = []
        for key, value in inputs.items():
            if (
                isinstance(key, str)
                and isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], int)
            ):
                signature.append((key, (value[0], value[1])))
        return tuple(sorted(signature))


def _cube_state(buffer: dict[str, object]) -> SimpleNamespace:
    """Build a minimal cube-state test double exposing a mutable buffer."""

    return SimpleNamespace(buffer=buffer)


def _service() -> NodeLinkGroupService:
    """Return the node-link service with deterministic endpoint discovery."""

    return NodeLinkGroupService(_NodeLinkEndpointProvider())


def _node(
    class_type: str,
    inputs: dict[str, object],
    *,
    from_cube: str | None | object = ...,
    from_node: str | None = None,
) -> dict[str, object]:
    """Build one node payload with optional node-link metadata."""

    node: dict[str, object] = {"class_type": class_type, "inputs": dict(inputs)}
    if from_cube is not ...:
        node["node_link"] = {"from_cube": from_cube, "from_node": from_node}
    return node


def _node_link_payload(node: dict[str, object]) -> dict[str, object]:
    """Return the node-link payload for one node."""

    return cast(dict[str, object], node["node_link"])
