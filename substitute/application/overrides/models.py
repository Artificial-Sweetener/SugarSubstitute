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

"""Define typed application models for the pinned override toolbar."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from substitute.application.node_behavior.models import ResolvedFieldSpec
from substitute.domain.node_behavior import OverridePinPolicy

OverrideValue = dict[str, Any]
OverrideMap = dict[str, OverrideValue]
OverrideSelectionMap = dict[str, bool]
OverrideFieldKey = tuple[str, str, str]


class OverrideParticipationKind(StrEnum):
    """Describe why one field can receive the current global override value."""

    NON_CHOICE = "non_choice"
    EXACT_OPTIONS = "exact_options"
    VALUE_SUPPORTED = "value_supported"


@dataclass(frozen=True)
class OverrideFieldParticipant:
    """Describe one workflow field affected by an active global override."""

    override_key: str
    cube_alias: str
    node_name: str
    field_key: str
    participation: OverrideParticipationKind

    @property
    def field_identity(self) -> OverrideFieldKey:
        """Return the workflow-local field identity for set membership checks."""

        return (self.cube_alias, self.node_name, self.field_key)


@dataclass(frozen=True)
class OverrideParticipationSnapshot:
    """Describe current field-level participation for active overrides."""

    participants_by_key: dict[str, tuple[OverrideFieldParticipant, ...]]
    eligible_fields_by_key: dict[str, tuple[OverrideFieldKey, ...]]

    def participant_fields(self) -> frozenset[OverrideFieldKey]:
        """Return every field identity that currently receives an override value."""

        return frozenset(
            participant.field_identity
            for participants in self.participants_by_key.values()
            for participant in participants
        )


@dataclass(frozen=True)
class OverrideToolbarCandidate:
    """Describe one pinnable workflow override candidate exposed to presentation."""

    override_key: str
    label: str
    pin_policy: OverridePinPolicy
    toolbar_order: int | None
    representative_spec: ResolvedFieldSpec


@dataclass(frozen=True)
class PinnedOverrideControl:
    """Describe one active toolbar control rendered from workflow override state."""

    override_key: str
    label: str
    value: Any
    spec: ResolvedFieldSpec


@dataclass(frozen=True)
class OverrideToolbarSnapshot:
    """Describe the complete toolbar candidate and active-control state."""

    candidates: list[OverrideToolbarCandidate]
    active_controls: list[PinnedOverrideControl]
    active_override_keys: tuple[str, ...]


__all__ = [
    "OverrideFieldKey",
    "OverrideFieldParticipant",
    "OverrideMap",
    "OverrideParticipationKind",
    "OverrideParticipationSnapshot",
    "OverrideSelectionMap",
    "OverrideToolbarCandidate",
    "OverrideToolbarSnapshot",
    "OverrideValue",
    "PinnedOverrideControl",
]
