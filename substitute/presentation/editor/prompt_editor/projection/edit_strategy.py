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

"""Define immutable source-edit classification and strategy contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol


class PromptSourceEditKind(IntEnum):
    """Describe the source-edit shape relevant to projection strategy."""

    NONE = 0
    DELETE = 1
    NEWLINE_INSERT = 2
    PLAIN_REPLACEMENT = 3


class PromptEditStrategy(IntEnum):
    """Name one projection strategy candidate in fallback order."""

    RESTORE_CHECKPOINT = 0
    DEFER_DIRECT_FEEDBACK = 1
    EXTEND_DEFERRED_WRAP = 2
    TRAILING_PLAIN_DELETE = 3
    TRAILING_NEWLINE_DELETE = 4
    TRAILING_NEWLINE_INSERT = 5
    TRAILING_PLAIN_INSERT = 6
    INCREMENTAL_PLAIN = 7
    DEFER_INCREMENTAL_WRAP = 8
    DEFER_TRANSIENT_FALLBACK = 9
    PUBLISH_PREBUILT_REFLOW = 10
    BUILD_CANONICAL_REFLOW = 11
    FULL_REBUILD = 12


class PromptEditClassificationInput(Protocol):
    """Expose already-computed facts without prescribing their request owner."""

    @property
    def edit_kind(self) -> PromptSourceEditKind:
        """Return the bounded source-edit shape."""

    @property
    def region_structure_requires_rebuild(self) -> bool:
        """Return whether regional topology changed."""

    @property
    def projection_topology_requires_rebuild(self) -> bool:
        """Return whether canonical projection topology changed."""

    @property
    def restore_checkpoint_available(self) -> bool:
        """Return whether exact history geometry is available."""

    @property
    def direct_deferred_feedback_allowed(self) -> bool:
        """Return whether the edit may publish feedback before layout."""

    @property
    def deferred_plain_edit_extendable(self) -> bool:
        """Return whether an existing deferred edit chain may extend."""

    @property
    def typed_character_requires_immediate_projection(self) -> bool:
        """Return whether syntax policy blocks the trailing fast path."""

    @property
    def syntax_sensitive_prefix_deferrable(self) -> bool:
        """Return whether incomplete syntax remains safe to defer."""

    @property
    def wrap_reflow_deferrable(self) -> bool:
        """Return whether wrap recovery may leave geometry stale-safe."""


@dataclass(frozen=True, slots=True)
class PromptEditClassificationFacts:
    """Carry already-known bounded facts used to select projection strategies."""

    edit_kind: PromptSourceEditKind
    region_structure_requires_rebuild: bool
    projection_topology_requires_rebuild: bool
    restore_checkpoint_available: bool
    direct_deferred_feedback_allowed: bool
    deferred_plain_edit_extendable: bool
    typed_character_requires_immediate_projection: bool
    syntax_sensitive_prefix_deferrable: bool
    wrap_reflow_deferrable: bool


@dataclass(frozen=True, slots=True)
class PromptEditStrategyPlan:
    """Describe the exact ordered candidates for one source edit."""

    candidates: tuple[PromptEditStrategy, ...]


def source_edit_kind(
    *,
    start: int | None,
    end: int | None,
    previous_source_text: str | None,
    replacement_text: str | None,
) -> PromptSourceEditKind:
    """Return the bounded classification shape for one optional source edit."""

    if start is None or end is None or previous_source_text is None:
        return PromptSourceEditKind.NONE
    if replacement_text == "":
        return PromptSourceEditKind.DELETE
    if replacement_text == "\n":
        return PromptSourceEditKind.NEWLINE_INSERT
    return PromptSourceEditKind.PLAIN_REPLACEMENT


__all__ = [
    "PromptEditClassificationFacts",
    "PromptEditClassificationInput",
    "PromptEditStrategy",
    "PromptEditStrategyPlan",
    "PromptSourceEditKind",
    "source_edit_kind",
]
