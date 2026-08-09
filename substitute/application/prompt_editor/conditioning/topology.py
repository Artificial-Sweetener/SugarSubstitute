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

"""Build reusable source and effective scopes for prompt conditioning batches."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.application.prompt_editor.conditioning.context import (
    PromptConditioningContext,
    PromptConditioningMode,
)
from substitute.application.prompt_editor.document.views import (
    PromptRegionStructureView,
)
from substitute.domain.prompt.document.ranges import SourceRange


class PromptConditioningScopeRole(StrEnum):
    """Describe one partition's role in an effective conditioning hierarchy."""

    CONDITION = "condition"
    GLOBAL = "global"
    REGION = "region"


@dataclass(frozen=True, slots=True)
class PromptConditioningScope:
    """Represent one source partition and its conditioning inheritance edge."""

    scope_id: str
    partition_index: int
    role: PromptConditioningScopeRole
    source_range: SourceRange
    parent_scope_id: str | None
    emits_condition: bool


@dataclass(frozen=True, slots=True)
class PromptConditioningTopology:
    """Expose immutable partition ownership and effective conditioning scopes."""

    context: PromptConditioningContext
    scopes: tuple[PromptConditioningScope, ...]

    def __post_init__(self) -> None:
        """Reject ambiguous scope identities and inheritance references."""

        scope_ids = {scope.scope_id for scope in self.scopes}
        if len(scope_ids) != len(self.scopes):
            raise ValueError("Conditioning scope identifiers must be unique.")
        if any(
            scope.parent_scope_id is not None and scope.parent_scope_id not in scope_ids
            for scope in self.scopes
        ):
            raise ValueError("Conditioning scope parents must exist in the topology.")

    @property
    def emitted_scopes(self) -> tuple[PromptConditioningScope, ...]:
        """Return the scopes that produce distinct conditioning outputs."""

        return tuple(scope for scope in self.scopes if scope.emits_condition)

    @property
    def root_scopes(self) -> tuple[PromptConditioningScope, ...]:
        """Return scopes without inherited conditioning state."""

        return tuple(scope for scope in self.scopes if scope.parent_scope_id is None)

    def scope(self, scope_id: str) -> PromptConditioningScope:
        """Return one scope by stable identifier."""

        for scope in self.scopes:
            if scope.scope_id == scope_id:
                return scope
        raise KeyError(scope_id)

    def scope_for_partition(self, partition_index: int) -> PromptConditioningScope:
        """Return the source scope owned by one parsed partition."""

        for scope in self.scopes:
            if scope.partition_index == partition_index:
                return scope
        raise KeyError(partition_index)

    def scope_at_source_position(
        self,
        source_position: int,
    ) -> PromptConditioningScope | None:
        """Return the partition containing a position, excluding separator lines."""

        for scope in self.scopes:
            source_range = scope.source_range
            if source_range.start <= source_position < source_range.end:
                return scope
        return None

    def children_of(
        self,
        scope_id: str,
    ) -> tuple[PromptConditioningScope, ...]:
        """Return direct conditioning descendants in source order."""

        return tuple(
            scope for scope in self.scopes if scope.parent_scope_id == scope_id
        )

    def effective_source_ranges(self, scope_id: str) -> tuple[SourceRange, ...]:
        """Return inherited and local ranges contributing to one emitted condition."""

        lineage: list[SourceRange] = []
        current = self.scope(scope_id)
        while True:
            lineage.append(current.source_range)
            if current.parent_scope_id is None:
                break
            current = self.scope(current.parent_scope_id)
        lineage.reverse()
        return tuple(lineage)


class PromptConditioningTopologyService:
    """Map parsed region partitions into graph-context conditioning scopes."""

    def build(
        self,
        context: PromptConditioningContext,
        region_structure: PromptRegionStructureView,
    ) -> PromptConditioningTopology:
        """Build conditioning scopes without reinterpreting separator syntax."""

        if not region_structure.separators:
            partition = region_structure.partitions[0]
            return PromptConditioningTopology(
                context=context,
                scopes=(
                    _scope_for_partition(
                        partition.index,
                        partition.source_start,
                        partition.source_end,
                        role=PromptConditioningScopeRole.CONDITION,
                        parent_scope_id=None,
                        emits_condition=True,
                    ),
                ),
            )
        if context.mode is PromptConditioningMode.REGIONAL:
            return _regional_topology(context, region_structure)
        return PromptConditioningTopology(
            context=context,
            scopes=tuple(
                _scope_for_partition(
                    partition.index,
                    partition.source_start,
                    partition.source_end,
                    role=PromptConditioningScopeRole.CONDITION,
                    parent_scope_id=None,
                    emits_condition=True,
                )
                for partition in region_structure.partitions
            ),
        )


def _regional_topology(
    context: PromptConditioningContext,
    region_structure: PromptRegionStructureView,
) -> PromptConditioningTopology:
    """Return one global source parent with independent emitted region children."""

    global_partition, *region_partitions = region_structure.partitions
    global_scope = _scope_for_partition(
        global_partition.index,
        global_partition.source_start,
        global_partition.source_end,
        role=PromptConditioningScopeRole.GLOBAL,
        parent_scope_id=None,
        emits_condition=False,
    )
    region_scopes = tuple(
        _scope_for_partition(
            partition.index,
            partition.source_start,
            partition.source_end,
            role=PromptConditioningScopeRole.REGION,
            parent_scope_id=global_scope.scope_id,
            emits_condition=True,
        )
        for partition in region_partitions
    )
    return PromptConditioningTopology(
        context=context,
        scopes=(global_scope, *region_scopes),
    )


def _scope_for_partition(
    partition_index: int,
    source_start: int,
    source_end: int,
    *,
    role: PromptConditioningScopeRole,
    parent_scope_id: str | None,
    emits_condition: bool,
) -> PromptConditioningScope:
    """Create one source scope with a partition-derived stable identifier."""

    return PromptConditioningScope(
        scope_id=f"partition:{partition_index}",
        partition_index=partition_index,
        role=role,
        source_range=SourceRange(source_start, source_end),
        parent_scope_id=parent_scope_id,
        emits_condition=emits_condition,
    )


__all__ = [
    "PromptConditioningScope",
    "PromptConditioningScopeRole",
    "PromptConditioningTopology",
    "PromptConditioningTopologyService",
]
