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

"""Define stack alias and ordering policies for workflow cube state."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from substitute.domain.common import CubeAlias, CubeBaseName


@dataclass
class StackManager:
    """Manage cube aliases, loaded cube mapping, and stack ordering."""

    cube_aliases: dict[CubeAlias, CubeBaseName] = field(default_factory=dict)
    loaded_cubes: dict[CubeAlias, Any] = field(default_factory=dict)
    stack_order: list[CubeAlias] = field(default_factory=list)

    def resolve_unique_alias(
        self,
        requested_alias: str,
        *,
        exclude_alias: CubeAlias | None = None,
    ) -> str:
        """Resolve one workflow-local alias against the active alias namespace."""

        active_aliases = set(self.cube_aliases)
        if exclude_alias is not None:
            active_aliases.discard(exclude_alias)

        normalized_alias = requested_alias.strip()
        if normalized_alias not in active_aliases:
            return normalized_alias

        alias_stem, requested_suffix = self._split_alias_seed(normalized_alias)
        suffix = requested_suffix + 1 if requested_suffix is not None else 2
        while f"{alias_stem} {suffix}" in active_aliases:
            suffix += 1
        return f"{alias_stem} {suffix}"

    def set_state(
        self,
        cube_aliases: dict[CubeAlias, CubeBaseName],
        loaded_cubes: dict[CubeAlias, Any],
        stack_order: list[CubeAlias],
    ) -> None:
        """Replace stack manager state from workflow-scoped snapshots."""
        self.cube_aliases = dict(cube_aliases)
        self.loaded_cubes = dict(loaded_cubes)
        self.stack_order = list(stack_order)

    def get_state(self) -> dict[str, object]:
        """Return a copy of all managed stack state collections."""
        return {
            "cube_aliases": dict(self.cube_aliases),
            "loaded_cubes": dict(self.loaded_cubes),
            "stack_order": list(self.stack_order),
        }

    def add_cube(self, cube_id: str, alias_name: str, cube_data: Any) -> None:
        """Add a cube alias and append it to the stack order."""
        self.cube_aliases[alias_name] = cube_id
        self.loaded_cubes[alias_name] = cube_data
        self.stack_order.append(alias_name)

    def remove_cube(self, alias_name: str) -> None:
        """Remove a cube alias from all managed collections."""
        self.cube_aliases.pop(alias_name, None)
        self.loaded_cubes.pop(alias_name, None)
        if alias_name in self.stack_order:
            self.stack_order.remove(alias_name)

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename a cube alias across alias map, loaded map, and order list."""
        if old_alias == new_alias:
            return
        if old_alias in self.cube_aliases:
            self.cube_aliases[new_alias] = self.cube_aliases.pop(old_alias)
        if old_alias in self.loaded_cubes:
            self.loaded_cubes[new_alias] = self.loaded_cubes.pop(old_alias)
        self.stack_order = [
            new_alias if alias == old_alias else alias for alias in self.stack_order
        ]

    def move_cube(self, from_index: int, to_index: int) -> None:
        """Move a cube alias inside stack order when indexes are in range."""
        if (
            from_index < 0
            or to_index < 0
            or from_index >= len(self.stack_order)
            or to_index >= len(self.stack_order)
        ):
            return
        alias = self.stack_order.pop(from_index)
        self.stack_order.insert(to_index, alias)

    def clear(self) -> None:
        """Clear all stack manager state."""
        self.cube_aliases.clear()
        self.loaded_cubes.clear()
        self.stack_order.clear()

    def to_dict(self) -> dict[str, object]:
        """Serialize stack manager state to a plain dictionary."""
        return {
            "cube_aliases": dict(self.cube_aliases),
            "loaded_cubes": dict(self.loaded_cubes),
            "stack_order": list(self.stack_order),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "StackManager":
        """Deserialize a stack manager state dictionary."""
        manager = cls()
        manager.set_state(
            cls._coerce_alias_map(data.get("cube_aliases")),
            cls._coerce_loaded_map(data.get("loaded_cubes")),
            cls._coerce_stack_order(data.get("stack_order")),
        )
        return manager

    @staticmethod
    def _coerce_alias_map(value: object) -> dict[CubeAlias, CubeBaseName]:
        """Return alias map from untyped serialized payload."""
        if not isinstance(value, dict):
            return {}
        return {str(alias): str(cube_id) for alias, cube_id in value.items()}

    @staticmethod
    def _coerce_loaded_map(value: object) -> dict[CubeAlias, Any]:
        """Return loaded-cube map from untyped serialized payload."""
        if not isinstance(value, dict):
            return {}
        return {str(alias): cube_data for alias, cube_data in value.items()}

    @staticmethod
    def _coerce_stack_order(value: object) -> list[CubeAlias]:
        """Return stack-order list from untyped serialized payload."""
        if not isinstance(value, list):
            return []
        return [str(alias) for alias in value]

    @staticmethod
    def _split_alias_seed(requested_alias: str) -> tuple[str, int | None]:
        """Split one alias seed into its stem and generated numeric suffix."""

        suffix_match = re.fullmatch(r"(.+?) ([2-9]\d*)", requested_alias)
        if suffix_match is None:
            return requested_alias, None
        return suffix_match.group(1), int(suffix_match.group(2))


__all__ = [
    "StackManager",
]
