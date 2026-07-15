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

"""Build whole-node link endpoint indexes from resolved editor behavior."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from substitute.domain.links.node_links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.node_behavior import ResolvedNodeBehavior

_VECTORSCOPE_EDITABLE_KEYS: Final[tuple[str, ...]] = (
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


class NodeLinkEndpointService:
    """Build whole-node link endpoints for the selectively supported node families."""

    def build_index(
        self,
        *,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
        resolved_nodes_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]],
        prompt_endpoint_index: PromptEndpointIndex,
    ) -> NodeLinkEndpointIndex:
        """Return node-link endpoints for prompt nodes and VectorscopeCC nodes."""

        endpoints: list[NodeLinkEndpoint] = []
        endpoints.extend(
            self._prompt_endpoints(
                resolved_nodes_by_alias=resolved_nodes_by_alias,
                prompt_endpoint_index=prompt_endpoint_index,
                cube_states=cube_states,
                stack_order=stack_order,
            )
        )
        endpoints.extend(
            self._vectorscope_endpoints(
                resolved_nodes_by_alias=resolved_nodes_by_alias,
                cube_states=cube_states,
                stack_order=stack_order,
            )
        )
        return NodeLinkEndpointIndex.from_endpoints(endpoints)

    def _prompt_endpoints(
        self,
        *,
        resolved_nodes_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]],
        prompt_endpoint_index: PromptEndpointIndex,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> tuple[NodeLinkEndpoint, ...]:
        """Return prompt endpoints represented as whole-node link endpoints."""

        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            roles = prompt_endpoint_index.roles_for_cube(cube_alias)
            for role in roles:
                prompt_endpoint = prompt_endpoint_index.endpoint_for(cube_alias, role)
                if prompt_endpoint is None:
                    continue
                behavior = resolved_nodes_by_alias.get(cube_alias, {}).get(
                    prompt_endpoint.node_name
                )
                if behavior is None:
                    continue
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name=prompt_endpoint.node_name,
                        class_type=behavior.class_type,
                        family=f"prompt:{role.value}",
                        editable_value_keys=(prompt_endpoint.field_key,),
                        graph_signature=self._graph_signature(
                            self._node_payload(
                                cube_states,
                                cube_alias,
                                prompt_endpoint.node_name,
                            ),
                            editable_value_keys=(prompt_endpoint.field_key,),
                        ),
                        reset_values={prompt_endpoint.field_key: ""},
                        linkable=prompt_endpoint.linkable,
                    )
                )
        return tuple(endpoints)

    def _vectorscope_endpoints(
        self,
        *,
        resolved_nodes_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]],
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> tuple[NodeLinkEndpoint, ...]:
        """Return enabled VectorscopeCC endpoints for whole-node linking."""

        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            behavior = resolved_nodes_by_alias.get(cube_alias, {}).get("vectorscopecc")
            if behavior is None or behavior.class_type != "VectorscopeCC":
                continue
            node_payload = self._node_payload(cube_states, cube_alias, "vectorscopecc")
            editable_keys = self._vectorscope_editable_keys(behavior, node_payload)
            if not editable_keys:
                continue
            endpoints.append(
                NodeLinkEndpoint(
                    cube_alias=cube_alias,
                    node_name="vectorscopecc",
                    class_type=behavior.class_type,
                    family="vectorscopecc",
                    editable_value_keys=editable_keys,
                    graph_signature=self._graph_signature(
                        node_payload,
                        editable_value_keys=editable_keys,
                    ),
                )
            )
        return tuple(endpoints)

    @staticmethod
    def _vectorscope_editable_keys(
        behavior: ResolvedNodeBehavior,
        node_payload: Mapping[str, object],
    ) -> tuple[str, ...]:
        """Return VectorscopeCC value keys that are currently editable literals."""

        inputs = node_payload.get("inputs")
        input_map = inputs if isinstance(inputs, Mapping) else {}
        keys: list[str] = []
        for key in _VECTORSCOPE_EDITABLE_KEYS:
            if key not in behavior.fields:
                continue
            value = input_map.get(key)
            if _is_comfy_connection(value):
                continue
            keys.append(key)
        return tuple(keys)

    @staticmethod
    def _node_payload(
        cube_states: Mapping[str, Any],
        cube_alias: str,
        node_name: str,
    ) -> Mapping[str, object]:
        """Return one raw node payload from cube state when available."""

        cube_state = cube_states.get(cube_alias)
        buffer = getattr(cube_state, "buffer", None)
        if not isinstance(buffer, Mapping):
            return {}
        nodes = buffer.get("nodes")
        if not isinstance(nodes, Mapping):
            return {}
        node = nodes.get(node_name)
        return node if isinstance(node, Mapping) else {}

    @staticmethod
    def _graph_signature(
        node_payload: Mapping[str, object],
        *,
        editable_value_keys: tuple[str, ...],
    ) -> tuple[tuple[str, object], ...]:
        """Return connection-shaped inputs that must match for node-link eligibility."""

        inputs = node_payload.get("inputs")
        if not isinstance(inputs, Mapping):
            return ()
        editable_keys = set(editable_value_keys)
        signature: list[tuple[str, object]] = []
        for key, value in inputs.items():
            if not isinstance(key, str) or key in editable_keys:
                continue
            if _is_comfy_connection(value):
                signature.append((key, (value[0], value[1])))
        return tuple(sorted(signature))


def _is_comfy_connection(value: object) -> bool:
    """Return whether a node input value is a Comfy graph connection."""

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


__all__ = ["NodeLinkEndpointService"]
