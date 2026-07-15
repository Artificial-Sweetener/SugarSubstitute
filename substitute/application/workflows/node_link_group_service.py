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

"""Apply whole-node link plans to workflow buffers across UI transitions."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from substitute.domain.links.node_links import (
    NodeLinkEndpointIndex,
    NodeLinkIdentity,
    NodeLinkMutation,
    NodeLinkReference,
    plan_default_links_for_unclaimed_downstream_endpoints,
    plan_normalization,
    plan_transition_reconciliation,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.node_link_group_service")


class NodeLinkEndpointProvider(Protocol):
    """Describe behavior capable of resolving whole-node link endpoints."""

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return whole-node link endpoints for the supplied cube stack."""


class NodeLinkGroupService:
    """Own node-link buffer mutations for spawn, selection, reorder, and removal."""

    def __init__(self, node_link_endpoint_provider: NodeLinkEndpointProvider) -> None:
        """Initialize the service with the authoritative endpoint provider."""

        self._node_link_endpoint_provider = node_link_endpoint_provider

    def reconcile_transition(
        self,
        *,
        previous_cube_states: Mapping[str, Any] | None,
        previous_stack_order: list[str] | None,
        current_cube_states: Mapping[str, Any] | None,
        current_stack_order: list[str] | None,
    ) -> None:
        """Reconcile node-link groups across one editor/workflow transition."""

        previous_buffers = self._extract_buffers(
            previous_cube_states,
            previous_stack_order,
        )
        current_buffers = self._extract_buffers(
            current_cube_states,
            current_stack_order,
        )
        if not current_buffers or current_stack_order is None:
            log_warning(
                _LOGGER,
                "Skipped node-link transition reconciliation",
                has_current_buffers=bool(current_buffers),
                current_stack_order=current_stack_order,
            )
            return

        current_index = self._build_endpoint_index(
            current_cube_states,
            current_stack_order,
        )
        if previous_buffers and previous_stack_order and previous_cube_states:
            previous_index = self._build_endpoint_index(
                previous_cube_states,
                previous_stack_order,
            )
            transition_mutations = plan_transition_reconciliation(
                previous_buffers,
                list(previous_stack_order),
                previous_index,
                current_buffers,
                list(current_stack_order),
                current_index,
            )
            self._apply_mutations(
                current_buffers,
                transition_mutations,
            )

        default_mutations = plan_default_links_for_unclaimed_downstream_endpoints(
            current_buffers,
            list(current_stack_order),
            current_index,
        )
        self._apply_mutations(
            current_buffers,
            default_mutations,
        )
        normalization_mutations = plan_normalization(
            current_buffers,
            list(current_stack_order),
            current_index,
        )
        self._apply_mutations(
            current_buffers,
            normalization_mutations,
        )

    def sanitize_current_state(
        self,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Normalize node links against the current stack order in place."""

        all_buffers = self._extract_buffers(cube_states, stack_order)
        if not all_buffers or stack_order is None:
            log_warning(
                _LOGGER,
                "Skipped node-link current-state sanitization",
                has_buffers=bool(all_buffers),
                stack_order=stack_order,
            )
            return
        endpoint_index = self._build_endpoint_index(cube_states, stack_order)
        default_mutations = plan_default_links_for_unclaimed_downstream_endpoints(
            all_buffers,
            list(stack_order),
            endpoint_index,
        )
        self._apply_mutations(
            all_buffers,
            default_mutations,
        )
        normalization_mutations = plan_normalization(
            all_buffers,
            list(stack_order),
            endpoint_index,
        )
        self._apply_mutations(
            all_buffers,
            normalization_mutations,
        )

    def apply_manual_selection(
        self,
        *,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
        cube_alias: str,
        identity: NodeLinkIdentity,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Apply one manual node-link selection while preserving local values."""

        all_buffers = self._extract_buffers(cube_states, stack_order)
        endpoint_index = self._build_endpoint_index(cube_states, stack_order)
        endpoint = endpoint_index.endpoint_for(cube_alias, identity)
        if endpoint is None:
            log_warning(
                _LOGGER,
                "Skipped node-link manual selection for missing endpoint",
                cube_alias=cube_alias,
                identity=repr(identity),
            )
            return
        node = (
            all_buffers.get(endpoint.cube_alias, {})
            .get("nodes", {})
            .get(endpoint.node_name)
        )
        if not isinstance(node, dict):
            log_warning(
                _LOGGER,
                "Skipped node-link manual selection for missing node",
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
            )
            return
        if from_cube is None or from_node is None:
            node["node_link"] = {"from_cube": None, "from_node": None}
            return

        target = endpoint_index.endpoint_for_node(from_cube, from_node, identity)
        if target is None or target.cube_alias == cube_alias:
            node["node_link"] = {"from_cube": None, "from_node": None}
            log_warning(
                _LOGGER,
                "Rejected node-link manual selection target",
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
                from_cube=from_cube,
                from_node=from_node,
                target_found=target is not None,
                target_is_self=target is not None and target.cube_alias == cube_alias,
            )
            return

        try:
            target_index = stack_order.index(target.cube_alias)
            cube_index = stack_order.index(cube_alias)
        except ValueError:
            node["node_link"] = {"from_cube": None, "from_node": None}
            log_warning(
                _LOGGER,
                "Rejected node-link manual selection with missing stack alias",
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
                from_cube=from_cube,
                from_node=from_node,
                stack_order=tuple(stack_order),
            )
            return

        if target_index >= cube_index:
            node["node_link"] = {"from_cube": None, "from_node": None}
            log_warning(
                _LOGGER,
                "Rejected node-link manual selection with downstream target",
                cube_alias=endpoint.cube_alias,
                node_name=endpoint.node_name,
                from_cube=target.cube_alias,
                from_node=target.node_name,
                target_index=target_index,
                cube_index=cube_index,
            )
            return
        node["node_link"] = {
            "from_cube": target.cube_alias,
            "from_node": target.node_name,
        }

    def _build_endpoint_index(
        self,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> NodeLinkEndpointIndex:
        """Return whole-node link endpoints for available cube state."""

        if cube_states is None or stack_order is None:
            return NodeLinkEndpointIndex()
        return self._node_link_endpoint_provider.build_node_link_endpoint_index(
            cube_states,
            list(stack_order),
        )

    @staticmethod
    def _extract_buffers(
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> dict[str, dict[str, Any]]:
        """Return a stack-ordered mapping of cube alias to mutable workflow buffer."""

        if cube_states is None:
            return {}
        if stack_order is None:
            aliases = list(cube_states.keys())
        else:
            aliases = [alias for alias in stack_order if alias in cube_states]

        buffers: dict[str, dict[str, Any]] = {}
        for alias in aliases:
            cube_state = cube_states.get(alias)
            buffer = getattr(cube_state, "buffer", None)
            if isinstance(buffer, dict):
                buffers[alias] = buffer
        return buffers

    @staticmethod
    def _apply_mutations(
        all_buffers: Mapping[str, dict[str, Any]],
        mutations: tuple[NodeLinkMutation, ...],
    ) -> None:
        """Apply node-link mutations in place to target workflow buffers."""

        for mutation in mutations:
            node = (
                all_buffers.get(mutation.cube_alias, {})
                .get("nodes", {})
                .get(mutation.node_name)
            )
            if not isinstance(node, dict):
                log_warning(
                    _LOGGER,
                    "Skipped node-link mutation for missing node",
                    cube_alias=mutation.cube_alias,
                    node_name=mutation.node_name,
                )
                continue
            if mutation.updates_node_link:
                node["node_link"] = _node_link_payload(mutation.node_link)
            if mutation.updates_values and isinstance(mutation.value_updates, Mapping):
                inputs = node.setdefault("inputs", {})
                if isinstance(inputs, dict):
                    inputs.update(dict(mutation.value_updates))


def _node_link_payload(
    value: NodeLinkReference | None | object,
) -> dict[str, str | None]:
    """Return the serialized node-link payload for a planned mutation."""

    if isinstance(value, NodeLinkReference):
        return {"from_cube": value.from_cube, "from_node": value.from_node}
    return {"from_cube": None, "from_node": None}


__all__ = ["NodeLinkEndpointProvider", "NodeLinkGroupService"]
