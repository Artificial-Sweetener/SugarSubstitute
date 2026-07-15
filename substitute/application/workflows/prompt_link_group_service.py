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

"""Adapt legacy prompt-link entry points onto generic whole-node linking."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from substitute.application.workflows.node_link_group_service import (
    NodeLinkGroupService,
)
from substitute.domain.links.node_links import NodeLinkEndpoint, NodeLinkEndpointIndex
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole


class PromptEndpointProvider(Protocol):
    """Describe behavior capable of resolving prompt endpoints for cube states."""

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return prompt endpoints for the supplied cube stack."""


class PromptLinkGroupService:
    """Provide prompt-link compatibility while storing canonical node-link metadata."""

    def __init__(self, prompt_endpoint_provider: PromptEndpointProvider) -> None:
        """Initialize the service with the authoritative prompt endpoint provider."""

        self._prompt_endpoint_provider = prompt_endpoint_provider
        self._node_endpoint_provider = _PromptNodeLinkEndpointProvider(
            prompt_endpoint_provider
        )
        self._node_link_group_service = NodeLinkGroupService(
            self._node_endpoint_provider
        )

    def reconcile_transition(
        self,
        *,
        previous_cube_states: Mapping[str, Any] | None,
        previous_stack_order: list[str] | None,
        current_cube_states: Mapping[str, Any] | None,
        current_stack_order: list[str] | None,
    ) -> None:
        """Reconcile prompt node-link groups across one editor/workflow transition."""

        self._migrate_legacy_prompt_links(previous_cube_states, previous_stack_order)
        self._migrate_legacy_prompt_links(current_cube_states, current_stack_order)
        self._node_link_group_service.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=current_cube_states,
            current_stack_order=current_stack_order,
        )

    def sanitize_current_state(
        self,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Normalize prompt node links against the current stack order in place."""

        self._migrate_legacy_prompt_links(cube_states, stack_order)
        self._node_link_group_service.sanitize_current_state(cube_states, stack_order)

    def apply_manual_selection(
        self,
        *,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
        cube_alias: str,
        role: PromptRole,
        from_cube: str | None,
    ) -> None:
        """Apply one manual prompt-link selection while preserving local prompt text."""

        self._migrate_legacy_prompt_links(cube_states, stack_order)
        endpoint_index = self._node_endpoint_provider.build_node_link_endpoint_index(
            cube_states,
            stack_order,
        )
        endpoint = self._endpoint_for_role(endpoint_index, cube_alias, role)
        if endpoint is None:
            return
        from_node = None
        if from_cube is not None:
            source = endpoint_index.endpoint_for(from_cube, endpoint.identity)
            if source is not None:
                from_node = source.node_name
        self._node_link_group_service.apply_manual_selection(
            cube_states=cube_states,
            stack_order=stack_order,
            cube_alias=cube_alias,
            identity=endpoint.identity,
            from_cube=from_cube,
            from_node=from_node,
        )
        self._node_link_group_service.sanitize_current_state(cube_states, stack_order)

    def _migrate_legacy_prompt_links(
        self,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Convert legacy prompt-link payloads to canonical node-link payloads."""

        if cube_states is None or stack_order is None:
            return
        prompt_index = self._prompt_endpoint_provider.build_prompt_endpoint_index(
            cube_states,
            list(stack_order),
        )
        for cube_alias in stack_order:
            for role in prompt_index.roles_for_cube(cube_alias):
                endpoint = prompt_index.endpoint_for(cube_alias, role)
                if endpoint is None:
                    continue
                node = _node_payload(cube_states, cube_alias, endpoint.node_name)
                if not isinstance(node, dict) or "prompt_link" not in node:
                    continue
                if "node_link" not in node:
                    node["node_link"] = self._node_link_from_prompt_link(
                        prompt_index,
                        role,
                        node.get("prompt_link"),
                    )
                node.pop("prompt_link", None)

    @staticmethod
    def _node_link_from_prompt_link(
        prompt_index: PromptEndpointIndex,
        role: PromptRole,
        prompt_link: object,
    ) -> dict[str, str | None]:
        """Return canonical node-link metadata for one legacy prompt-link payload."""

        if not isinstance(prompt_link, Mapping):
            return {"from_cube": None, "from_node": None}
        from_cube = prompt_link.get("from_cube")
        if not isinstance(from_cube, str) or not from_cube:
            return {"from_cube": None, "from_node": None}
        source_endpoint = prompt_index.endpoint_for(from_cube, role)
        if source_endpoint is None:
            return {"from_cube": None, "from_node": None}
        return {"from_cube": from_cube, "from_node": source_endpoint.node_name}

    @staticmethod
    def _endpoint_for_role(
        endpoint_index: NodeLinkEndpointIndex,
        cube_alias: str,
        role: PromptRole,
    ) -> NodeLinkEndpoint | None:
        """Return the unique prompt node-link endpoint for one cube and role."""

        family = f"prompt:{role.value}"
        for identity in endpoint_index.identities_for_cube(cube_alias):
            if identity.family != family:
                continue
            return endpoint_index.endpoint_for(cube_alias, identity)
        return None


class LegacyPromptLinkMigrationService:
    """Migrate persisted prompt_link metadata to canonical node_link metadata."""

    def __init__(self, prompt_endpoint_provider: PromptEndpointProvider) -> None:
        """Store the prompt endpoint provider used for compatibility migration."""

        self._prompt_endpoint_provider = prompt_endpoint_provider

    def migrate(
        self,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Convert legacy prompt-link payloads in-place when stack context exists."""

        if cube_states is None or stack_order is None:
            return
        prompt_index = self._prompt_endpoint_provider.build_prompt_endpoint_index(
            cube_states,
            list(stack_order),
        )
        for cube_alias in stack_order:
            for role in prompt_index.roles_for_cube(cube_alias):
                endpoint = prompt_index.endpoint_for(cube_alias, role)
                if endpoint is None:
                    continue
                node = _node_payload(cube_states, cube_alias, endpoint.node_name)
                if not isinstance(node, dict) or "prompt_link" not in node:
                    continue
                if "node_link" not in node:
                    node["node_link"] = (
                        PromptLinkGroupService._node_link_from_prompt_link(
                            prompt_index,
                            role,
                            node.get("prompt_link"),
                        )
                    )
                node.pop("prompt_link", None)


class _PromptNodeLinkEndpointProvider:
    """Build prompt-only node-link endpoints from resolved prompt endpoints."""

    def __init__(self, prompt_endpoint_provider: PromptEndpointProvider) -> None:
        """Store the prompt endpoint provider used by the compatibility facade."""

        self._prompt_endpoint_provider = prompt_endpoint_provider

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return prompt endpoints represented as whole-node link endpoints."""

        prompt_index = self._prompt_endpoint_provider.build_prompt_endpoint_index(
            cube_states,
            list(stack_order),
        )
        endpoints: list[NodeLinkEndpoint] = []
        for cube_alias in stack_order:
            for role in prompt_index.roles_for_cube(cube_alias):
                prompt_endpoint = prompt_index.endpoint_for(cube_alias, role)
                if prompt_endpoint is None:
                    continue
                node = _node_payload(cube_states, cube_alias, prompt_endpoint.node_name)
                class_type = ""
                if isinstance(node, Mapping) and isinstance(
                    node.get("class_type"), str
                ):
                    class_type = str(node["class_type"])
                endpoints.append(
                    NodeLinkEndpoint(
                        cube_alias=cube_alias,
                        node_name=prompt_endpoint.node_name,
                        class_type=class_type,
                        family=f"prompt:{role.value}",
                        editable_value_keys=(prompt_endpoint.field_key,),
                        graph_signature=_graph_signature(
                            node,
                            editable_value_keys=(prompt_endpoint.field_key,),
                        ),
                        reset_values={prompt_endpoint.field_key: ""},
                        linkable=prompt_endpoint.linkable,
                    )
                )
        return NodeLinkEndpointIndex.from_endpoints(endpoints)


def _node_payload(
    cube_states: Mapping[str, Any],
    cube_alias: str,
    node_name: str,
) -> dict[str, Any] | Mapping[str, object]:
    """Return one raw node payload from cube state when available."""

    cube_state = cube_states.get(cube_alias)
    buffer = getattr(cube_state, "buffer", None)
    if not isinstance(buffer, Mapping):
        return {}
    nodes = buffer.get("nodes")
    if not isinstance(nodes, Mapping):
        return {}
    node = nodes.get(node_name)
    return node if isinstance(node, dict) else {}


def _graph_signature(
    node_payload: Mapping[str, object],
    *,
    editable_value_keys: tuple[str, ...],
) -> tuple[tuple[str, object], ...]:
    """Return connection-shaped prompt-node inputs outside the editable prompt field."""

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
    """Return whether a value is a Comfy graph connection."""

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


__all__ = [
    "LegacyPromptLinkMigrationService",
    "PromptEndpointProvider",
    "PromptLinkGroupService",
]
