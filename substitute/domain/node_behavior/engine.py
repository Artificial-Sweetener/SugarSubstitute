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

"""Compute unified node display decisions, hidden fields, and reveal entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from substitute.domain.links.node_links import NodeLinkEndpointIndex
    from substitute.domain.links.prompt_endpoints import PromptEndpointIndex

from .models import (
    ActivationDefault,
    ActivationSwitchRole,
    ActivationSwitchSource,
    EnabledSwitchPolicy,
    NodeActivationOverride,
    NodeActivationPolicy,
    NodeDisplayDecision,
    NodeVisibilityOverride,
    PackageBehaviorPatch,
    ResolvedNodeBehavior,
    RevealMenuEntry,
    RevealMode,
)


def _default_prompt_endpoint_index() -> PromptEndpointIndex:
    """Return an empty prompt endpoint index without creating import cycles."""

    from substitute.domain.links.prompt_endpoints import PromptEndpointIndex

    return PromptEndpointIndex()


def _default_node_link_endpoint_index() -> NodeLinkEndpointIndex:
    """Return an empty node-link endpoint index without creating import cycles."""

    from substitute.domain.links.node_links import NodeLinkEndpointIndex

    return NodeLinkEndpointIndex()


@dataclass(frozen=True)
class EditorBehaviorContext:
    """Describe the immutable runtime snapshot consumed by the engine."""

    stack_order: tuple[str, ...]
    cubes: Mapping[str, Any]
    behaviors_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]]
    workflow_overrides: Mapping[str, object]
    search_hidden_keys: frozenset[object]
    override_hidden_field_keys: frozenset[object] = frozenset()
    prompt_endpoint_index: PromptEndpointIndex = field(
        default_factory=_default_prompt_endpoint_index
    )
    node_link_endpoint_index: NodeLinkEndpointIndex = field(
        default_factory=_default_node_link_endpoint_index
    )
    node_search_text: str | None = None
    search_matching_nodes: frozenset[tuple[str, str]] | None = None


def _cube_buffer(cube_state: Any) -> dict[str, Any]:
    """Return the mutable cube buffer when present."""

    buffer = getattr(cube_state, "buffer", None)
    return buffer if isinstance(buffer, dict) else {}


def _buffer_node(cube_state: Any, node_name: str) -> dict[str, Any]:
    """Return one node payload from the cube buffer."""

    return _cube_buffer(cube_state).get("nodes", {}).get(node_name, {}) or {}


def _buffer_activation_override(
    cube_state: Any,
    node_name: str,
) -> NodeActivationOverride:
    """Return the persisted explicit activation override for one node."""

    node = _buffer_node(cube_state, node_name)
    if "enabled" not in node:
        return NodeActivationOverride()
    return NodeActivationOverride(explicit_enabled=bool(node.get("enabled")))


def _buffer_visibility_override(
    cube_state: Any,
    node_name: str,
) -> NodeVisibilityOverride:
    """Return the persisted explicit reveal override for one node."""

    node = _buffer_node(cube_state, node_name)
    if node.get("revealed") is True:
        return NodeVisibilityOverride(explicit_revealed=True)
    return NodeVisibilityOverride()


def _has_active_node_link(node_payload: Mapping[str, Any]) -> bool:
    """Return whether a node has active canonical whole-node link metadata."""

    node_link = node_payload.get("node_link")
    return isinstance(node_link, Mapping) and node_link.get("from_cube") is not None


def _active_node_link_source(node_payload: Mapping[str, Any]) -> tuple[str, str] | None:
    """Return active whole-node link source cube/node metadata when present."""

    node_link = node_payload.get("node_link")
    if not isinstance(node_link, Mapping):
        return None
    from_cube = node_link.get("from_cube")
    from_node = node_link.get("from_node")
    if isinstance(from_cube, str) and from_cube and isinstance(from_node, str):
        return from_cube, from_node
    return None


def _is_authored_bypass_node(node_payload: Mapping[str, Any]) -> bool:
    """Return whether the cube author bypassed this node in the source graph."""

    return node_payload.get("mode") == 4


def _matches_hide_strings(
    *,
    package_patch: PackageBehaviorPatch | None,
    node_name: str,
    class_type: str,
) -> bool:
    """Return whether a declarative package patch hides this node by name or class."""

    if package_patch is None:
        return False
    return bool(
        node_name in package_patch.hidden_node_names
        or class_type in package_patch.hidden_class_types
        or node_name in package_patch.hidden_strings
        or class_type in package_patch.hidden_strings
    )


def _enabled_switch_visible(
    behavior: ResolvedNodeBehavior,
    *,
    revealable: bool,
) -> bool:
    """Return whether generic activation policy should expose a title switch."""

    if behavior.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER:
        return False
    return (
        revealable or behavior.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    )


def resolve_graph_activation_switches(
    *,
    stack_order: tuple[str, ...],
    behaviors_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]],
) -> Mapping[tuple[str, str], bool]:
    """Return graph-level visibility for inferred typed-transform switches."""

    candidates_by_group: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for alias in stack_order:
        for node_name, behavior in behaviors_by_alias.get(alias, {}).items():
            if not _is_inferred_typed_transform_candidate(behavior):
                continue
            for signal_type in behavior.card.activation_signal_types:
                candidates_by_group.setdefault((alias, signal_type), set()).add(
                    (alias, node_name)
                )

    decisions: dict[tuple[str, str], bool] = {}
    for candidates in candidates_by_group.values():
        show_switch = len(candidates) > 1
        for candidate in candidates:
            decisions[candidate] = decisions.get(candidate, False) or show_switch
    return decisions


def _is_inferred_typed_transform_candidate(
    behavior: ResolvedNodeBehavior,
) -> bool:
    """Return whether a resolved behavior needs graph-level switch arbitration."""

    return bool(
        behavior.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
        and behavior.card.enabled_switch_source == ActivationSwitchSource.INFERRED
        and behavior.card.activation_switch_role == ActivationSwitchRole.TYPED_TRANSFORM
        and behavior.card.activation_signal_types
    )


def _resolve_show_enabled_switch(
    *,
    alias: str,
    node_name: str,
    behavior: ResolvedNodeBehavior,
    policy: NodeActivationPolicy,
    graph_switches: Mapping[tuple[str, str], bool],
) -> bool:
    """Return final title-switch visibility after local and graph policy."""

    if behavior.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER:
        return False
    if _is_inferred_typed_transform_candidate(behavior):
        return bool(
            policy.show_enabled_switch and graph_switches.get((alias, node_name))
        )
    return policy.show_enabled_switch


def _activation_default_for_policy(
    *,
    behavior: ResolvedNodeBehavior,
    fallback_active: bool,
) -> bool:
    """Return policy activation while preserving AUTO fallback behavior."""

    if behavior.card.activation_default == ActivationDefault.ENABLED:
        return True
    if behavior.card.activation_default == ActivationDefault.DISABLED:
        return False
    return fallback_active


def _activation_can_ignore_visibility(behavior: ResolvedNodeBehavior) -> bool:
    """Return whether activation is explicitly independent from card visibility."""

    return behavior.card.activation_default == ActivationDefault.ENABLED


def _resolve_activation_policy(
    *,
    alias: str,
    node_name: str,
    behavior: ResolvedNodeBehavior,
    package_patch: PackageBehaviorPatch | None,
    authored_bypass: bool,
) -> NodeActivationPolicy:
    """Return the policy-derived activation defaults for one node."""

    if authored_bypass:
        return NodeActivationPolicy(
            default_active=_activation_default_for_policy(
                behavior=behavior,
                fallback_active=False,
            ),
            default_visible=False,
            revealable=True,
            show_enabled_switch=_enabled_switch_visible(behavior, revealable=True),
            hidden_reason="policy:authored-bypass",
        )

    hidden_by_package = _matches_hide_strings(
        package_patch=package_patch,
        node_name=node_name,
        class_type=behavior.class_type,
    )
    hidden_by_behavior = behavior.card.hidden
    if hidden_by_package or hidden_by_behavior:
        hidden_reason = (
            "policy:package-hide" if hidden_by_package else "policy:override-hide"
        )
        revealable = behavior.card.reveal_mode == RevealMode.MENU
        return NodeActivationPolicy(
            default_active=_activation_default_for_policy(
                behavior=behavior,
                fallback_active=False,
            ),
            default_visible=False,
            revealable=revealable,
            show_enabled_switch=_enabled_switch_visible(
                behavior,
                revealable=revealable,
            ),
            hidden_reason=hidden_reason,
        )

    revealable = behavior.card.reveal_mode == RevealMode.MENU
    return NodeActivationPolicy(
        default_active=_activation_default_for_policy(
            behavior=behavior,
            fallback_active=True,
        ),
        default_visible=True,
        revealable=revealable,
        show_enabled_switch=_enabled_switch_visible(
            behavior,
            revealable=revealable,
        ),
        hidden_reason=None,
    )


def _resolve_effective_override(
    *,
    override: NodeActivationOverride,
    behavior: ResolvedNodeBehavior,
) -> tuple[bool | None, bool]:
    """Return the effective explicit override and whether legacy force-visible supplied it."""

    if override.explicit_enabled is not None:
        return override.explicit_enabled, False
    if behavior.card.force_visible:
        return True, True
    return None, False


def _matches_node_search(
    *,
    alias: str,
    search_text: str | None,
    search_matching_nodes: frozenset[tuple[str, str]] | None,
    node_name: str,
    class_type: str,
) -> bool:
    """Return whether the node matches the active node-search text."""

    if search_matching_nodes is not None:
        return (alias, node_name) in search_matching_nodes
    needle = (search_text or "").strip().lower()
    if not needle:
        return True
    return needle in node_name.lower() or needle in class_type.lower()


def _resolve_reason(
    *,
    policy: NodeActivationPolicy,
    explicit_override: bool | None,
    explicit_revealed: bool | None,
    effective_enabled: bool,
    policy_visible: bool,
    hard_hidden: bool,
    legacy_force_visible: bool,
    search_matches: bool,
) -> str:
    """Return the user-facing reason string for one node decision."""

    if not search_matches:
        return "search:node-filter"
    if hard_hidden and policy.hidden_reason is not None:
        return policy.hidden_reason
    if legacy_force_visible:
        return "legacy:force-visible"
    if explicit_override is True:
        return "explicit:enabled"
    if explicit_override is False:
        return "explicit:disabled"
    if effective_enabled:
        return "default:active"
    if explicit_revealed is True:
        return "explicit:revealed"
    if not policy_visible and policy.hidden_reason is not None:
        return policy.hidden_reason
    return "default:inactive"


def compute_card_decisions(
    ctx: EditorBehaviorContext,
    *,
    declarative_by_alias: Mapping[str, PackageBehaviorPatch | None],
) -> dict[str, dict[str, NodeDisplayDecision]]:
    """Compute one display decision per cube/node using resolved behavior metadata."""

    graph_switches = resolve_graph_activation_switches(
        stack_order=ctx.stack_order,
        behaviors_by_alias=ctx.behaviors_by_alias,
    )
    decisions: dict[str, dict[str, NodeDisplayDecision]] = {}
    for alias in ctx.stack_order:
        cube_state = ctx.cubes.get(alias)
        if cube_state is None:
            continue
        per_node: dict[str, NodeDisplayDecision] = {}
        package_patch = declarative_by_alias.get(alias)
        for node_name, behavior in ctx.behaviors_by_alias.get(alias, {}).items():
            node_payload = _buffer_node(cube_state, node_name)
            override = _buffer_activation_override(cube_state, node_name)
            visibility_override = _buffer_visibility_override(cube_state, node_name)
            explicit_override, legacy_force_visible = _resolve_effective_override(
                override=override,
                behavior=behavior,
            )
            policy = _resolve_activation_policy(
                alias=alias,
                node_name=node_name,
                behavior=behavior,
                package_patch=package_patch,
                authored_bypass=_is_authored_bypass_node(node_payload),
            )

            activation_enabled = (
                explicit_override
                if explicit_override is not None
                else policy.default_active
            )
            hard_hidden = behavior.card.hidden and not policy.revealable
            policy_visible = (
                False
                if hard_hidden
                else (
                    visibility_override.explicit_revealed is True
                    or legacy_force_visible
                    or policy.default_visible
                )
            )
            effective_enabled = bool(
                activation_enabled
                and (policy_visible or _activation_can_ignore_visibility(behavior))
            )

            search_matches = _matches_node_search(
                alias=alias,
                search_text=ctx.node_search_text,
                search_matching_nodes=ctx.search_matching_nodes,
                node_name=node_name,
                class_type=behavior.class_type,
            )
            visible = policy_visible and search_matches
            reason = _resolve_reason(
                policy=policy,
                explicit_override=explicit_override,
                explicit_revealed=visibility_override.explicit_revealed,
                effective_enabled=bool(effective_enabled),
                policy_visible=bool(policy_visible),
                hard_hidden=hard_hidden,
                legacy_force_visible=legacy_force_visible,
                search_matches=search_matches,
            )
            show_enabled_switch = _resolve_show_enabled_switch(
                alias=alias,
                node_name=node_name,
                behavior=behavior,
                policy=policy,
                graph_switches=graph_switches,
            )
            link_source = (
                _active_node_link_source(node_payload)
                if isinstance(node_payload, dict)
                else None
            )
            node_link_active = link_source is not None
            if link_source is not None:
                source_alias, source_node = link_source
                source_decision = decisions.get(source_alias, {}).get(source_node)
                if source_decision is not None:
                    effective_enabled = bool(policy_visible and source_decision.enabled)
                    reason = "node-link:inherited-enabled"

            per_node[node_name] = NodeDisplayDecision(
                visible=bool(visible),
                enabled=bool(effective_enabled),
                reason=reason,
                revealable=policy.revealable,
                reveal_checked=bool(policy_visible),
                show_enabled_switch=show_enabled_switch,
                policy_default_enabled=policy.default_active,
                policy_default_visible=policy.default_visible,
                explicit_override=explicit_override,
                explicit_revealed=visibility_override.explicit_revealed,
                node_link_active=node_link_active,
            )
        decisions[alias] = per_node
    return decisions


def compute_hidden_field_keys(ctx: EditorBehaviorContext) -> dict[str, set[object]]:
    """Compute merged hidden-field keys per cube alias."""

    hidden_by_alias: dict[str, set[object]] = {
        alias: set() for alias in ctx.stack_order
    }
    for alias in ctx.stack_order:
        cube_state = ctx.cubes.get(alias)
        if cube_state is None:
            continue
        for node_name, behavior in ctx.behaviors_by_alias.get(alias, {}).items():
            for field_key, field_behavior in behavior.fields.items():
                if field_behavior.hidden:
                    hidden_by_alias[alias].add((alias, node_name, field_key))
                if not ctx.override_hidden_field_keys:
                    override_key = (
                        field_behavior.override_behavior.override_key or field_key
                    )
                    if override_key in ctx.workflow_overrides:
                        hidden_by_alias[alias].add((alias, node_name, field_key))
            node_payload = _buffer_node(cube_state, node_name)
            if isinstance(node_payload, dict) and _has_active_node_link(node_payload):
                for identity in ctx.node_link_endpoint_index.identities_for_cube(alias):
                    node_link_endpoint = ctx.node_link_endpoint_index.endpoint_for(
                        alias,
                        identity,
                    )
                    if (
                        node_link_endpoint is None
                        or node_link_endpoint.node_name != node_name
                    ):
                        continue
                    for field_key in node_link_endpoint.editable_value_keys:
                        hidden_key = (alias, node_name, field_key)
                        hidden_by_alias[alias].add(hidden_key)
        for key in ctx.search_hidden_keys:
            if isinstance(key, str):
                hidden_by_alias[alias].add(key)
            elif isinstance(key, tuple) and key and key[0] == alias:
                hidden_by_alias[alias].add(key)
        for key in ctx.override_hidden_field_keys:
            if isinstance(key, str):
                hidden_by_alias[alias].add(key)
            elif isinstance(key, tuple) and key and key[0] == alias:
                hidden_by_alias[alias].add(key)
    return hidden_by_alias


def compute_all_hidden_keys(
    *,
    overrides: Mapping[str, object] | None = None,
    cubes: Mapping[str, Any] | None = None,
    prompt_endpoint_index: PromptEndpointIndex | None = None,
    node_link_endpoint_index: NodeLinkEndpointIndex | None = None,
    search_hidden_keys: set[object] | None = None,
    override_hidden_field_keys: set[object] | None = None,
) -> set[object]:
    """Return merged hidden-field keys from overrides, node links, and search."""

    _ = prompt_endpoint_index
    hidden_keys: set[object] = set()
    if overrides:
        hidden_keys.update(str(key) for key in overrides.keys())

    cube_map: Mapping[str, Any] = cubes if isinstance(cubes, Mapping) else {}
    for alias, cube in cube_map.items():
        buffer = getattr(cube, "buffer", cube if isinstance(cube, dict) else {})
        if isinstance(buffer, dict) and node_link_endpoint_index is not None:
            nodes = buffer.get("nodes", {})
            if isinstance(nodes, Mapping):
                for identity in node_link_endpoint_index.identities_for_cube(alias):
                    endpoint = node_link_endpoint_index.endpoint_for(alias, identity)
                    if endpoint is None:
                        continue
                    node = nodes.get(endpoint.node_name, {})
                    if not isinstance(node, dict) or not _has_active_node_link(node):
                        continue
                    hidden_keys.update(
                        (alias, endpoint.node_name, field_key)
                        for field_key in endpoint.editable_value_keys
                    )

        ui_payload = getattr(cube, "ui", None)
        if not isinstance(ui_payload, dict):
            continue
        package_patch = ui_payload.get("node_behavior")
        if not isinstance(package_patch, PackageBehaviorPatch):
            continue
        for node_name, field_keys in package_patch.hidden_fields_by_node.items():
            for field_key in field_keys:
                hidden_keys.add((alias, node_name, field_key))

    if search_hidden_keys:
        hidden_keys.update(search_hidden_keys)
    if override_hidden_field_keys:
        hidden_keys.update(override_hidden_field_keys)
    return hidden_keys


def compute_reveal_entries(
    ctx: EditorBehaviorContext,
    decisions: Mapping[str, Mapping[str, NodeDisplayDecision]],
) -> dict[str, list[RevealMenuEntry]]:
    """Compute reveal-menu entries directly from resolved node display decisions."""

    entries_by_alias: dict[str, list[RevealMenuEntry]] = {}
    for alias in ctx.stack_order:
        entries: list[RevealMenuEntry] = []
        for node_name, decision in decisions.get(alias, {}).items():
            if not decision.revealable:
                continue
            entries.append(
                RevealMenuEntry(
                    alias=alias,
                    node_name=node_name,
                    label=node_name,
                    checked=decision.reveal_checked,
                )
            )
        entries_by_alias[alias] = entries
    return entries_by_alias


def compute_editor_behavior(
    ctx: EditorBehaviorContext,
    *,
    declarative_by_alias: Mapping[str, PackageBehaviorPatch | None],
) -> tuple[
    dict[str, dict[str, NodeDisplayDecision]],
    dict[str, set[object]],
    dict[str, list[RevealMenuEntry]],
]:
    """Compute the complete runtime editor behavior snapshot."""

    decisions = compute_card_decisions(ctx, declarative_by_alias=declarative_by_alias)
    hidden_keys = compute_hidden_field_keys(ctx)
    reveal_entries = compute_reveal_entries(ctx, decisions)
    return decisions, hidden_keys, reveal_entries


__all__ = [
    "EditorBehaviorContext",
    "compute_card_decisions",
    "compute_all_hidden_keys",
    "compute_editor_behavior",
    "compute_hidden_field_keys",
    "compute_reveal_entries",
]
