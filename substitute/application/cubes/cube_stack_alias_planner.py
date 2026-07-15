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

"""Plan cart-visible cube aliases without mutating workflow state."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from substitute.application.cubes.cube_stack_draft_models import (
    CubeStackDraftEntry,
    cube_stack_draft_result,
)
from substitute.domain.workflow import StackManager


@dataclass(frozen=True)
class CubeStackPlannedAlias:
    """Describe one locked or assignable alias resolved for a cart entry."""

    draft_id: str
    requested_alias: str
    planned_alias: str
    locked: bool


@dataclass(frozen=True)
class CubeStackAliasPlan:
    """Expose planned aliases by stable draft entry identity."""

    aliases_by_draft_id: dict[str, CubeStackPlannedAlias]

    def alias_for(self, draft_id: str) -> CubeStackPlannedAlias:
        """Return the planned alias record for one draft entry."""

        return self.aliases_by_draft_id[draft_id]

    def planned_alias_for(self, draft_id: str) -> str:
        """Return the visible and commit-ready alias for one draft entry."""

        return self.alias_for(draft_id).planned_alias


def plan_cube_stack_aliases(
    entries: Sequence[CubeStackDraftEntry],
) -> CubeStackAliasPlan:
    """Plan cart aliases while preserving workflow-owned existing aliases.

    Existing entries reserve their current alias before any new entry is assigned.
    New entries then resolve in cart order from their current display-name seed.
    """

    validated_entries = cube_stack_draft_result(list(entries)).entries
    manager = StackManager()
    aliases_by_draft_id: dict[str, CubeStackPlannedAlias] = {}

    for entry in validated_entries:
        if entry.source != "existing":
            continue
        existing_alias = entry.existing_alias
        if existing_alias is None:
            continue
        aliases_by_draft_id[entry.draft_id] = CubeStackPlannedAlias(
            draft_id=entry.draft_id,
            requested_alias=existing_alias,
            planned_alias=existing_alias,
            locked=True,
        )
        manager.add_cube(entry.cube_id, existing_alias, None)

    for entry in validated_entries:
        if entry.source == "existing":
            continue
        requested_alias = entry.display_name
        planned_alias = manager.resolve_unique_alias(requested_alias)
        aliases_by_draft_id[entry.draft_id] = CubeStackPlannedAlias(
            draft_id=entry.draft_id,
            requested_alias=requested_alias,
            planned_alias=planned_alias,
            locked=False,
        )
        manager.add_cube(entry.cube_id, planned_alias, None)

    return CubeStackAliasPlan(aliases_by_draft_id=aliases_by_draft_id)


__all__ = [
    "CubeStackAliasPlan",
    "CubeStackPlannedAlias",
    "plan_cube_stack_aliases",
]
