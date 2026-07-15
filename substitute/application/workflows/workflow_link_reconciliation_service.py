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

"""Coordinate workflow link reconciliation at stable orchestration boundaries."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any, Mapping, Protocol, cast

from substitute.application.workflows.node_link_group_service import (
    NodeLinkEndpointProvider,
    NodeLinkGroupService,
)
from substitute.application.workflows.prompt_link_group_service import (
    LegacyPromptLinkMigrationService,
    PromptEndpointProvider,
)
from substitute.domain.links import NodeLinkEndpointIndex, NodeLinkIdentity
from substitute.domain.links.prompt_endpoints import PromptEndpointIndex
from substitute.domain.node_behavior import PromptRole

_EndpointIndexCacheKey = tuple[Hashable, ...]


class _CombinedEndpointProvider(Protocol):
    """Describe providers that can resolve both link indexes from one pass."""

    def build_link_endpoint_indexes(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> tuple[PromptEndpointIndex, NodeLinkEndpointIndex]:
        """Return prompt and node-link endpoint indexes together."""


class _ScopedEndpointIndexCache:
    """Share endpoint index resolution inside one reconciliation operation."""

    def __init__(
        self,
        *,
        prompt_endpoint_provider: PromptEndpointProvider,
        node_link_endpoint_provider: NodeLinkEndpointProvider,
    ) -> None:
        """Store providers and initialize empty per-operation caches."""

        self._prompt_endpoint_provider = prompt_endpoint_provider
        self._node_link_endpoint_provider = node_link_endpoint_provider
        same_endpoint_provider = id(prompt_endpoint_provider) == id(
            node_link_endpoint_provider
        )
        self._combined_provider = (
            cast(_CombinedEndpointProvider, prompt_endpoint_provider)
            if same_endpoint_provider
            and hasattr(
                prompt_endpoint_provider,
                "build_link_endpoint_indexes",
            )
            else None
        )
        self._prompt_indexes: dict[_EndpointIndexCacheKey, PromptEndpointIndex] = {}
        self._node_link_indexes: dict[
            _EndpointIndexCacheKey,
            NodeLinkEndpointIndex,
        ] = {}

    def build_prompt_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> PromptEndpointIndex:
        """Return a cached prompt endpoint index for one cube stack."""

        key = self._cache_key(cube_states, stack_order)
        prompt_index = self._prompt_indexes.get(key)
        if prompt_index is not None:
            return prompt_index
        if self._combined_provider is not None:
            self._populate_combined_indexes(key, cube_states, stack_order)
            return self._prompt_indexes[key]
        prompt_index = self._prompt_endpoint_provider.build_prompt_endpoint_index(
            cube_states,
            list(stack_order),
        )
        self._prompt_indexes[key] = prompt_index
        return prompt_index

    def build_node_link_endpoint_index(
        self,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> NodeLinkEndpointIndex:
        """Return a cached whole-node endpoint index for one cube stack."""

        key = self._cache_key(cube_states, stack_order)
        node_link_index = self._node_link_indexes.get(key)
        if node_link_index is not None:
            return node_link_index
        if self._combined_provider is not None:
            self._populate_combined_indexes(key, cube_states, stack_order)
            return self._node_link_indexes[key]
        node_link_index = (
            self._node_link_endpoint_provider.build_node_link_endpoint_index(
                cube_states,
                list(stack_order),
            )
        )
        self._node_link_indexes[key] = node_link_index
        return node_link_index

    def _populate_combined_indexes(
        self,
        key: _EndpointIndexCacheKey,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> None:
        """Populate both endpoint indexes from one combined provider call."""

        if key in self._prompt_indexes and key in self._node_link_indexes:
            return
        if self._combined_provider is None:
            raise RuntimeError("No combined endpoint provider is available.")
        prompt_index, node_link_index = (
            self._combined_provider.build_link_endpoint_indexes(
                cube_states,
                list(stack_order),
            )
        )
        self._prompt_indexes[key] = prompt_index
        self._node_link_indexes[key] = node_link_index

    @staticmethod
    def _cache_key(
        cube_states: Mapping[str, Any],
        stack_order: list[str],
    ) -> _EndpointIndexCacheKey:
        """Return an identity key for one stack of mutable cube states."""

        cube_tokens = tuple(
            (
                alias,
                id(cube_states.get(alias)),
                id(getattr(cube_states.get(alias), "buffer", None)),
            )
            for alias in stack_order
        )
        return id(cube_states), tuple(stack_order), cube_tokens


class WorkflowLinkReconciliationService:
    """Apply canonical node-link policy to workflow buffers in place.

    The editor and shell both need to reconcile links, but the correct lifecycle
    boundary is not always an editor widget insertion. This service keeps that
    application-level policy reusable so batch orchestration migrates legacy
    prompt links and then reconciles canonical node links once.
    """

    def __init__(
        self,
        *,
        prompt_endpoint_provider: PromptEndpointProvider,
        node_link_endpoint_provider: NodeLinkEndpointProvider,
    ) -> None:
        """Store the endpoint-backed services used to mutate workflow buffers."""

        self._node_link_endpoint_provider = node_link_endpoint_provider
        self._prompt_endpoint_provider = prompt_endpoint_provider

    def _scoped_link_services(
        self,
    ) -> tuple[LegacyPromptLinkMigrationService, NodeLinkGroupService]:
        """Return reconciliation services sharing one endpoint-index cache."""

        endpoint_cache = _ScopedEndpointIndexCache(
            prompt_endpoint_provider=self._prompt_endpoint_provider,
            node_link_endpoint_provider=self._node_link_endpoint_provider,
        )
        return (
            LegacyPromptLinkMigrationService(endpoint_cache),
            NodeLinkGroupService(node_link_endpoint_provider=endpoint_cache),
        )

    def reconcile_transition(
        self,
        *,
        previous_cube_states: Mapping[str, Any] | None,
        previous_stack_order: list[str] | None,
        current_cube_states: Mapping[str, Any] | None,
        current_stack_order: list[str] | None,
    ) -> None:
        """Migrate legacy prompt links and reconcile canonical node links."""

        migration_service, node_link_group_service = self._scoped_link_services()
        migration_service.migrate(
            previous_cube_states,
            previous_stack_order,
        )
        migration_service.migrate(
            current_cube_states,
            current_stack_order,
        )
        node_link_group_service.reconcile_transition(
            previous_cube_states=previous_cube_states,
            previous_stack_order=previous_stack_order,
            current_cube_states=current_cube_states,
            current_stack_order=current_stack_order,
        )

    def sanitize_current_state(
        self,
        *,
        cube_states: Mapping[str, Any] | None,
        stack_order: list[str] | None,
    ) -> None:
        """Migrate legacy prompt links and normalize canonical node links."""

        migration_service, node_link_group_service = self._scoped_link_services()
        migration_service.migrate(
            cube_states,
            stack_order,
        )
        node_link_group_service.sanitize_current_state(
            cube_states,
            stack_order,
        )

    def apply_manual_prompt_selection(
        self,
        *,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
        cube_alias: str,
        role: PromptRole,
        from_cube: str | None,
    ) -> None:
        """Apply one user-selected prompt link through canonical node selection."""

        migration_service, node_link_group_service = self._scoped_link_services()
        migration_service.migrate(cube_states, stack_order)
        endpoint_index = node_link_group_service._build_endpoint_index(
            cube_states,
            list(stack_order),
        )
        endpoint = endpoint_index.prompt_endpoint_for(cube_alias, role)
        if endpoint is None:
            return
        from_node = None
        if from_cube is not None:
            source_endpoint = endpoint_index.endpoint_for(from_cube, endpoint.identity)
            if source_endpoint is not None:
                from_node = source_endpoint.node_name
        node_link_group_service.apply_manual_selection(
            cube_states=cube_states,
            stack_order=stack_order,
            cube_alias=cube_alias,
            identity=endpoint.identity,
            from_cube=from_cube,
            from_node=from_node,
        )
        node_link_group_service.sanitize_current_state(cube_states, stack_order)

    def apply_manual_node_selection(
        self,
        *,
        cube_states: Mapping[str, Any],
        stack_order: list[str],
        cube_alias: str,
        identity: NodeLinkIdentity,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Apply one user-selected whole-node link through the shared workflow service."""

        _migration_service, node_link_group_service = self._scoped_link_services()
        node_link_group_service.apply_manual_selection(
            cube_states=cube_states,
            stack_order=stack_order,
            cube_alias=cube_alias,
            identity=identity,
            from_cube=from_cube,
            from_node=from_node,
        )
        node_link_group_service.sanitize_current_state(
            cube_states,
            stack_order,
        )


__all__ = ["WorkflowLinkReconciliationService"]
