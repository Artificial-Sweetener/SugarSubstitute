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

"""Define prompt endpoint identity for role-based prompt linking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from substitute.domain.node_behavior.models import PromptRole


@dataclass(frozen=True)
class PromptEndpoint:
    """Identify the concrete node field that stores one semantic prompt."""

    cube_alias: str
    role: PromptRole
    node_name: str
    field_key: str
    linkable: bool = True


@dataclass(frozen=True)
class PromptEndpointIndex:
    """Expose prompt endpoints by cube alias and semantic role."""

    endpoints: tuple[PromptEndpoint, ...] = ()
    ambiguous_keys: frozenset[tuple[str, PromptRole]] = frozenset()

    @classmethod
    def from_endpoints(
        cls,
        endpoints: Iterable[PromptEndpoint],
    ) -> PromptEndpointIndex:
        """Build an index and mark duplicate linkable cube-role endpoints ambiguous."""

        ordered = tuple(endpoints)
        counts: dict[tuple[str, PromptRole], int] = {}
        for endpoint in ordered:
            if not endpoint.linkable:
                continue
            key = (endpoint.cube_alias, endpoint.role)
            counts[key] = counts.get(key, 0) + 1
        ambiguous = frozenset(key for key, count in counts.items() if count > 1)
        return cls(endpoints=ordered, ambiguous_keys=ambiguous)

    def endpoint_for(
        self,
        cube_alias: str,
        role: PromptRole,
    ) -> PromptEndpoint | None:
        """Return the unique linkable endpoint for one cube and role."""

        key = (cube_alias, role)
        if key in self.ambiguous_keys:
            return None
        for endpoint in self.endpoints:
            if (
                endpoint.linkable
                and endpoint.cube_alias == cube_alias
                and endpoint.role == role
            ):
                return endpoint
        return None

    def endpoints_for_role(self, role: PromptRole) -> tuple[PromptEndpoint, ...]:
        """Return unique linkable endpoints for one role in index order."""

        result: list[PromptEndpoint] = []
        seen_aliases: set[str] = set()
        for endpoint in self.endpoints:
            if endpoint.role != role or endpoint.cube_alias in seen_aliases:
                continue
            resolved = self.endpoint_for(endpoint.cube_alias, role)
            if resolved is None:
                continue
            result.append(resolved)
            seen_aliases.add(endpoint.cube_alias)
        return tuple(result)

    def roles(self) -> tuple[PromptRole, ...]:
        """Return roles represented by unique linkable endpoints."""

        result: list[PromptRole] = []
        for endpoint in self.endpoints:
            if endpoint.role in result:
                continue
            if self.endpoint_for(endpoint.cube_alias, endpoint.role) is None:
                continue
            result.append(endpoint.role)
        return tuple(result)

    def roles_for_cube(self, cube_alias: str) -> tuple[PromptRole, ...]:
        """Return linkable prompt roles exposed by one cube alias."""

        result: list[PromptRole] = []
        for endpoint in self.endpoints:
            if endpoint.cube_alias != cube_alias or endpoint.role in result:
                continue
            if self.endpoint_for(cube_alias, endpoint.role) is not None:
                result.append(endpoint.role)
        return tuple(result)

    def first_earlier_endpoint(
        self,
        stack_order: Sequence[str],
        cube_alias: str,
        role: PromptRole,
    ) -> PromptEndpoint | None:
        """Return the earliest previous endpoint for a cube and role."""

        try:
            cube_index = list(stack_order).index(cube_alias)
        except ValueError:
            return None
        for alias in stack_order[:cube_index]:
            endpoint = self.endpoint_for(alias, role)
            if endpoint is not None:
                return endpoint
        return None

    def valid_link_targets(
        self,
        stack_order: Sequence[str],
        cube_alias: str,
        role: PromptRole,
    ) -> tuple[PromptEndpoint, ...]:
        """Return linkable same-role endpoints before the requested cube."""

        try:
            cube_index = list(stack_order).index(cube_alias)
        except ValueError:
            return ()
        targets: list[PromptEndpoint] = []
        for alias in stack_order[:cube_index]:
            endpoint = self.endpoint_for(alias, role)
            if endpoint is not None:
                targets.append(endpoint)
        return tuple(targets)


__all__ = ["PromptEndpoint", "PromptEndpointIndex"]
