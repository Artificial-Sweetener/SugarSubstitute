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

"""Plan whole-node link groups, defaults, normalization, and transition rebasing."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, TypeAlias

from substitute.domain.node_behavior.models import PromptRole

NodeBuffers: TypeAlias = Mapping[str, Mapping[str, Any]]
_UNCHANGED: Final[object] = object()
_PROMPT_FAMILY_PREFIX: Final[str] = "prompt:"


@dataclass(frozen=True)
class NodeLinkIdentity:
    """Identify one compatible whole-node link family."""

    family: str
    node_name: str
    class_type: str
    editable_value_keys: tuple[str, ...]
    graph_signature: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class NodeLinkEndpoint:
    """Identify one concrete node that can participate in whole-node linking."""

    cube_alias: str
    node_name: str
    class_type: str
    family: str
    editable_value_keys: tuple[str, ...]
    graph_signature: tuple[tuple[str, object], ...] = ()
    reset_values: Mapping[str, object] = field(
        default_factory=dict,
        compare=False,
        hash=False,
    )
    linkable: bool = field(default=True, compare=False)

    @property
    def identity(self) -> NodeLinkIdentity:
        """Return the compatibility identity shared by eligible linked nodes."""

        return NodeLinkIdentity(
            family=self.family,
            node_name=self.node_name,
            class_type=self.class_type,
            editable_value_keys=self.editable_value_keys,
            graph_signature=self.graph_signature,
        )


@dataclass(frozen=True)
class NodeLinkReference:
    """Reference a source node for one node-link follower."""

    from_cube: str
    from_node: str


@dataclass(frozen=True)
class NodeLinkEndpointIndex:
    """Expose whole-node link endpoints by cube alias and compatibility identity."""

    endpoints: tuple[NodeLinkEndpoint, ...] = ()
    ambiguous_keys: frozenset[tuple[str, NodeLinkIdentity]] = frozenset()

    @classmethod
    def from_endpoints(
        cls,
        endpoints: Iterable[NodeLinkEndpoint],
    ) -> NodeLinkEndpointIndex:
        """Build an index and mark duplicate linkable cube-identity endpoints ambiguous."""

        ordered = tuple(endpoints)
        counts: dict[tuple[str, NodeLinkIdentity], int] = {}
        for endpoint in ordered:
            if not endpoint.linkable:
                continue
            key = (endpoint.cube_alias, endpoint.identity)
            counts[key] = counts.get(key, 0) + 1
        ambiguous = frozenset(key for key, count in counts.items() if count > 1)
        return cls(endpoints=ordered, ambiguous_keys=ambiguous)

    def endpoint_for(
        self,
        cube_alias: str,
        identity: NodeLinkIdentity,
    ) -> NodeLinkEndpoint | None:
        """Return the unique linkable endpoint for one cube and identity."""

        key = (cube_alias, identity)
        if key in self.ambiguous_keys:
            return None
        for endpoint in self.endpoints:
            if (
                endpoint.linkable
                and endpoint.cube_alias == cube_alias
                and endpoint.identity == identity
            ):
                return endpoint
        return None

    def endpoint_for_node(
        self,
        cube_alias: str,
        node_name: str,
        identity: NodeLinkIdentity,
    ) -> NodeLinkEndpoint | None:
        """Return the unique endpoint matching one cube, node, and identity."""

        endpoint = self.endpoint_for(cube_alias, identity)
        if endpoint is None or endpoint.node_name != node_name:
            return None
        return endpoint

    def identities(self) -> tuple[NodeLinkIdentity, ...]:
        """Return identities represented by unique linkable endpoints."""

        result: list[NodeLinkIdentity] = []
        for endpoint in self.endpoints:
            identity = endpoint.identity
            if identity in result:
                continue
            if self.endpoint_for(endpoint.cube_alias, identity) is None:
                continue
            result.append(identity)
        return tuple(result)

    def identities_for_cube(self, cube_alias: str) -> tuple[NodeLinkIdentity, ...]:
        """Return linkable node identities exposed by one cube alias."""

        result: list[NodeLinkIdentity] = []
        for endpoint in self.endpoints:
            identity = endpoint.identity
            if endpoint.cube_alias != cube_alias or identity in result:
                continue
            if self.endpoint_for(cube_alias, identity) is not None:
                result.append(identity)
        return tuple(result)

    def prompt_endpoint_for(
        self,
        cube_alias: str,
        role: PromptRole,
    ) -> NodeLinkEndpoint | None:
        """Return the unique prompt-family endpoint for one cube and role."""

        family = _prompt_family(role)
        for identity in self.identities_for_cube(cube_alias):
            if identity.family != family:
                continue
            return self.endpoint_for(cube_alias, identity)
        return None

    def prompt_roles_for_cube(self, cube_alias: str) -> tuple[PromptRole, ...]:
        """Return prompt roles represented by linkable node-link endpoints."""

        roles: list[PromptRole] = []
        for identity in self.identities_for_cube(cube_alias):
            role = _role_from_prompt_family(identity.family)
            if role is None or role in roles:
                continue
            roles.append(role)
        return tuple(roles)

    def prompt_text_endpoints(self) -> tuple[NodeLinkEndpoint, ...]:
        """Return linkable prompt-family endpoints used by prompt text consumers."""

        return tuple(
            endpoint
            for endpoint in self.endpoints
            if endpoint.linkable
            and _role_from_prompt_family(endpoint.family) is not None
            and self.endpoint_for(endpoint.cube_alias, endpoint.identity) is not None
        )

    def first_earlier_endpoint(
        self,
        stack_order: list[str],
        cube_alias: str,
        identity: NodeLinkIdentity,
    ) -> NodeLinkEndpoint | None:
        """Return the earliest previous endpoint for a cube and identity."""

        try:
            cube_index = stack_order.index(cube_alias)
        except ValueError:
            return None
        for alias in stack_order[:cube_index]:
            endpoint = self.endpoint_for(alias, identity)
            if endpoint is not None:
                return endpoint
        return None

    def valid_link_targets(
        self,
        stack_order: list[str],
        cube_alias: str,
        identity: NodeLinkIdentity,
    ) -> tuple[NodeLinkEndpoint, ...]:
        """Return linkable same-identity endpoints before the requested cube."""

        try:
            cube_index = stack_order.index(cube_alias)
        except ValueError:
            return ()
        targets: list[NodeLinkEndpoint] = []
        for alias in stack_order[:cube_index]:
            endpoint = self.endpoint_for(alias, identity)
            if endpoint is not None:
                targets.append(endpoint)
        return tuple(targets)


@dataclass(frozen=True)
class NodeLinkGroup:
    """Describe one normalized whole-node sharing group."""

    identity: NodeLinkIdentity
    anchor: NodeLinkEndpoint
    members: tuple[NodeLinkEndpoint, ...]
    effective_values: Mapping[str, object]


@dataclass(frozen=True)
class NodeLinkMutation:
    """Describe one node-link buffer mutation planned by the domain layer."""

    cube_alias: str
    node_name: str
    node_link: NodeLinkReference | None | object = _UNCHANGED
    value_updates: Mapping[str, object] | object = _UNCHANGED

    @property
    def updates_node_link(self) -> bool:
        """Return whether this mutation changes node-link metadata."""

        return self.node_link is not _UNCHANGED

    @property
    def updates_values(self) -> bool:
        """Return whether this mutation changes local dormant node values."""

        return self.value_updates is not _UNCHANGED


def plan_default_links_for_unclaimed_downstream_endpoints(
    all_buffers: NodeBuffers,
    stack_order: list[str],
    endpoint_index: NodeLinkEndpointIndex,
) -> tuple[NodeLinkMutation, ...]:
    """Plan default links for downstream endpoints with no captured intent."""

    mutations: list[NodeLinkMutation] = []
    for identity in endpoint_index.identities():
        for cube_alias in stack_order:
            endpoint = endpoint_index.endpoint_for(cube_alias, identity)
            if endpoint is None:
                continue
            node = _endpoint_node(all_buffers, endpoint)
            if node is None or "node_link" in node:
                continue
            anchor = endpoint_index.first_earlier_endpoint(
                stack_order,
                cube_alias,
                identity,
            )
            if anchor is None:
                continue
            mutations.append(
                _mutation_for(
                    endpoint,
                    node_link=NodeLinkReference(anchor.cube_alias, anchor.node_name),
                )
            )
    return tuple(mutations)


def plan_normalization(
    all_buffers: NodeBuffers,
    stack_order: list[str],
    endpoint_index: NodeLinkEndpointIndex,
) -> tuple[NodeLinkMutation, ...]:
    """Plan direct-to-anchor node-link normalization for the current order."""

    mutations: list[NodeLinkMutation] = []
    for identity in endpoint_index.identities():
        for group in normalize_node_link_groups(
            all_buffers,
            stack_order,
            identity,
            endpoint_index,
        ):
            anchor_node = _endpoint_node(all_buffers, group.anchor)
            if anchor_node is None:
                continue
            if _raw_node_link(anchor_node) is not None:
                mutations.append(_mutation_for(group.anchor, node_link=None))
            for member in group.members[1:]:
                member_node = _endpoint_node(all_buffers, member)
                if member_node is None:
                    continue
                expected = NodeLinkReference(
                    group.anchor.cube_alias,
                    group.anchor.node_name,
                )
                if _raw_node_link(member_node) != expected:
                    mutations.append(_mutation_for(member, node_link=expected))
    return tuple(mutations)


def plan_transition_reconciliation(
    previous_buffers: NodeBuffers,
    previous_stack_order: list[str],
    previous_endpoint_index: NodeLinkEndpointIndex,
    current_buffers: NodeBuffers,
    current_stack_order: list[str],
    current_endpoint_index: NodeLinkEndpointIndex,
) -> tuple[NodeLinkMutation, ...]:
    """Plan node-link reconciliation across one workflow stack transition."""

    current_aliases = set(current_stack_order)
    mutations: list[NodeLinkMutation] = []
    for identity in previous_endpoint_index.identities():
        previous_groups = normalize_node_link_groups(
            previous_buffers,
            previous_stack_order,
            identity,
            previous_endpoint_index,
        )
        for group in previous_groups:
            surviving_members = [
                endpoint
                for alias in current_stack_order
                if alias in current_aliases
                if (endpoint := current_endpoint_index.endpoint_for(alias, identity))
                is not None
                and alias in {member.cube_alias for member in group.members}
            ]
            if not surviving_members:
                continue

            removed_members = {member.cube_alias for member in group.members} - {
                member.cube_alias for member in surviving_members
            }
            new_anchor = surviving_members[0]
            anchor_changed = new_anchor.cube_alias != group.anchor.cube_alias
            if anchor_changed:
                mutations.append(
                    _mutation_for(
                        new_anchor,
                        node_link=None,
                        value_updates=group.effective_values,
                    )
                )
                preserve_linked_locals = bool(removed_members)
                for member in surviving_members[1:]:
                    updates = (
                        _UNCHANGED
                        if preserve_linked_locals
                        else _reset_values_for(member)
                    )
                    mutations.append(
                        _mutation_for(
                            member,
                            node_link=NodeLinkReference(
                                new_anchor.cube_alias,
                                new_anchor.node_name,
                            ),
                            value_updates=updates,
                        )
                    )
                continue

            anchor_node = _endpoint_node(current_buffers, group.anchor)
            if anchor_node is not None and _raw_node_link(anchor_node) is not None:
                mutations.append(_mutation_for(group.anchor, node_link=None))
            for member in surviving_members[1:]:
                member_node = _endpoint_node(current_buffers, member)
                if member_node is None:
                    continue
                expected = NodeLinkReference(
                    group.anchor.cube_alias,
                    group.anchor.node_name,
                )
                if _raw_node_link(member_node) != expected:
                    mutations.append(_mutation_for(member, node_link=expected))
    return tuple(mutations)


def normalize_node_link_groups(
    all_buffers: NodeBuffers,
    stack_order: list[str],
    identity: NodeLinkIdentity,
    endpoint_index: NodeLinkEndpointIndex,
) -> tuple[NodeLinkGroup, ...]:
    """Return normalized whole-node link groups for one identity in stack order."""

    members = _member_endpoints(stack_order, identity, endpoint_index)
    if not members:
        return ()

    nodes_by_endpoint = {
        (endpoint.cube_alias, endpoint.node_name): _endpoint_node(
            all_buffers,
            endpoint,
        )
        for endpoint in members
    }
    index_by_alias = {
        endpoint.cube_alias: index for index, endpoint in enumerate(members)
    }
    endpoint_by_alias = {endpoint.cube_alias: endpoint for endpoint in members}
    groups_by_anchor: dict[NodeLinkEndpoint, list[NodeLinkEndpoint]] = {}
    for endpoint in members:
        anchor = _resolve_anchor_endpoint(
            endpoint=endpoint,
            nodes_by_endpoint=nodes_by_endpoint,
            index_by_alias=index_by_alias,
            endpoint_by_alias=endpoint_by_alias,
            identity=identity,
        )
        groups_by_anchor.setdefault(anchor, []).append(endpoint)

    groups: list[NodeLinkGroup] = []
    for anchor in members:
        group_members = groups_by_anchor.get(anchor)
        if not group_members:
            continue
        anchor_node = _endpoint_node(all_buffers, anchor)
        if anchor_node is None:
            continue
        groups.append(
            NodeLinkGroup(
                identity=identity,
                anchor=anchor,
                members=tuple(group_members),
                effective_values=_value_snapshot(anchor_node, anchor),
            )
        )
    return tuple(groups)


def update_node_link_references_on_rename(
    all_buffers: Mapping[str, Mapping[str, Any]],
    old_alias: str,
    new_alias: str,
) -> None:
    """Rewrite node-link references when a source cube alias is renamed."""

    for cube in all_buffers.values():
        nodes = cube.get("nodes", {})
        if not isinstance(nodes, Mapping):
            continue
        for node in nodes.values():
            if not isinstance(node, dict):
                continue
            link = node.get("node_link", {})
            if isinstance(link, dict) and link.get("from_cube") == old_alias:
                link["from_cube"] = new_alias


def _prompt_family(role: PromptRole) -> str:
    """Return the node-link family name for one prompt role."""

    return f"{_PROMPT_FAMILY_PREFIX}{role.value}"


def _role_from_prompt_family(family: str) -> PromptRole | None:
    """Return a prompt role when the node-link family names a prompt endpoint."""

    if not family.startswith(_PROMPT_FAMILY_PREFIX):
        return None
    role_value = family.removeprefix(_PROMPT_FAMILY_PREFIX)
    for role in PromptRole:
        if role.value == role_value:
            return role
    return None


def _mutation_for(
    endpoint: NodeLinkEndpoint,
    *,
    node_link: NodeLinkReference | None | object = _UNCHANGED,
    value_updates: Mapping[str, object] | object = _UNCHANGED,
) -> NodeLinkMutation:
    """Return a mutation targeting the provided endpoint."""

    return NodeLinkMutation(
        cube_alias=endpoint.cube_alias,
        node_name=endpoint.node_name,
        node_link=node_link,
        value_updates=value_updates,
    )


def _member_endpoints(
    stack_order: list[str],
    identity: NodeLinkIdentity,
    endpoint_index: NodeLinkEndpointIndex,
) -> list[NodeLinkEndpoint]:
    """Return stack-ordered endpoints containing the requested identity."""

    return [
        endpoint
        for alias in stack_order
        if (endpoint := endpoint_index.endpoint_for(alias, identity)) is not None
    ]


def _nodes_for_alias(
    all_buffers: NodeBuffers,
    cube_alias: str,
) -> Mapping[str, Any]:
    """Return the node mapping for one cube alias when available."""

    cube_buffer = all_buffers.get(cube_alias, {})
    nodes = cube_buffer.get("nodes", {})
    return nodes if isinstance(nodes, Mapping) else {}


def _endpoint_node(
    all_buffers: NodeBuffers,
    endpoint: NodeLinkEndpoint,
) -> dict[str, Any] | None:
    """Return the endpoint node payload when it exists."""

    node = _nodes_for_alias(all_buffers, endpoint.cube_alias).get(endpoint.node_name)
    return node if isinstance(node, dict) else None


def _raw_node_link(node_payload: Mapping[str, Any]) -> NodeLinkReference | None:
    """Return the stored node-link source when present."""

    node_link = node_payload.get("node_link")
    if not isinstance(node_link, Mapping):
        return None
    from_cube = node_link.get("from_cube")
    from_node = node_link.get("from_node")
    if (
        isinstance(from_cube, str)
        and from_cube
        and isinstance(from_node, str)
        and from_node
    ):
        return NodeLinkReference(from_cube=from_cube, from_node=from_node)
    return None


def _value_snapshot(
    node_payload: Mapping[str, Any],
    endpoint: NodeLinkEndpoint,
) -> Mapping[str, object]:
    """Return local editable values stored on one endpoint node."""

    inputs = node_payload.get("inputs")
    if not isinstance(inputs, Mapping):
        return {}
    return {
        key: inputs.get(key) for key in endpoint.editable_value_keys if key in inputs
    }


def _reset_values_for(endpoint: NodeLinkEndpoint) -> Mapping[str, object] | object:
    """Return follower reset values or no-op when the endpoint keeps dormant locals."""

    if not endpoint.reset_values:
        return _UNCHANGED
    return dict(endpoint.reset_values)


def _resolve_anchor_endpoint(
    *,
    endpoint: NodeLinkEndpoint,
    nodes_by_endpoint: Mapping[tuple[str, str], dict[str, Any] | None],
    index_by_alias: Mapping[str, int],
    endpoint_by_alias: Mapping[str, NodeLinkEndpoint],
    identity: NodeLinkIdentity,
) -> NodeLinkEndpoint:
    """Return the normalized anchor endpoint for one member in one node-link group."""

    current = endpoint
    while True:
        node = nodes_by_endpoint.get((current.cube_alias, current.node_name))
        if node is None:
            return endpoint
        target = _raw_node_link(node)
        if target is None:
            return current
        if (
            target.from_cube == current.cube_alias
            and target.from_node == current.node_name
        ):
            return current
        target_endpoint = endpoint_by_alias.get(target.from_cube)
        if (
            target_endpoint is None
            or target_endpoint.node_name != target.from_node
            or target_endpoint.identity != identity
        ):
            return current
        target_index = index_by_alias.get(target_endpoint.cube_alias)
        current_index = index_by_alias.get(current.cube_alias)
        if target_index is None or current_index is None:
            return current
        if target_index >= current_index:
            return current
        current = target_endpoint


__all__ = [
    "NodeLinkEndpoint",
    "NodeLinkEndpointIndex",
    "NodeLinkGroup",
    "NodeLinkIdentity",
    "NodeLinkMutation",
    "NodeLinkReference",
    "normalize_node_link_groups",
    "plan_default_links_for_unclaimed_downstream_endpoints",
    "plan_normalization",
    "plan_transition_reconciliation",
    "update_node_link_references_on_rename",
]
