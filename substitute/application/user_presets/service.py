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

"""Coordinate user preset queries and updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import uuid4

from substitute.domain.common import JsonObject
from substitute.domain.user_presets import (
    DimensionPresetPayload,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
    canonical_dimension_payload,
)


class UserPresetRepository(Protocol):
    """Persist and retrieve user preset records."""

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored user presets."""

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Persist user presets."""


@dataclass(frozen=True)
class DimensionPresetSection:
    """Group dimension presets for one matching association."""

    association: UserPresetAssociation
    presets: tuple[UserPreset, ...]


@dataclass(frozen=True)
class DimensionPresetListing:
    """Return global and context-matched dimension preset sections."""

    global_presets: tuple[UserPreset, ...]
    association_sections: tuple[DimensionPresetSection, ...]


@dataclass(frozen=True)
class PromptStringPresetSection:
    """Group prompt presets by matching association specificity."""

    title: str
    association: UserPresetAssociation
    presets: tuple[UserPreset, ...]


@dataclass(frozen=True)
class PromptStringPresetListing:
    """Expose prompt presets sorted for menu rendering."""

    sections: tuple[PromptStringPresetSection, ...]


@dataclass(frozen=True)
class NodeInputPresetSection:
    """Group node input presets for one matching association."""

    association: UserPresetAssociation
    presets: tuple[UserPreset, ...]


@dataclass(frozen=True)
class NodeInputPresetListing:
    """Return node input presets grouped by matching save scope."""

    sections: tuple[NodeInputPresetSection, ...]


class UserPresetService:
    """Coordinate user preset queries and updates."""

    def __init__(
        self,
        repository: UserPresetRepository,
        *,
        id_factory: Callable[[], str] | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        """Store preset persistence collaborators."""

        self._repository = repository
        self._id_factory = id_factory
        self._clock = clock or _utc_now_iso

    def list_dimension_presets(
        self,
        associations: tuple[UserPresetAssociation, ...],
    ) -> DimensionPresetListing:
        """Return global and association-matched dimension presets."""

        presets = _sorted_dimension_presets(self._repository.load_presets())
        global_presets = tuple(
            preset for preset in presets if _has_global_association(preset)
        )
        sections: list[DimensionPresetSection] = []
        for association in associations:
            matching_presets = tuple(
                preset
                for preset in presets
                if any(
                    _same_association_target(candidate, association)
                    for candidate in preset.associations
                )
                and association.scope is UserPresetAssociationScope.MODEL_FAMILY
            )
            if matching_presets:
                sections.append(
                    DimensionPresetSection(
                        association=association,
                        presets=matching_presets,
                    )
                )
        return DimensionPresetListing(
            global_presets=global_presets,
            association_sections=tuple(sections),
        )

    def save_dimension_preset(
        self,
        *,
        width: int,
        height: int,
        association: UserPresetAssociation,
    ) -> UserPreset:
        """Create or merge a dimension preset for one association."""

        payload = canonical_dimension_payload(width, height)
        presets = list(self._repository.load_presets())
        for index, preset in enumerate(presets):
            if preset.kind is not UserPresetKind.DIMENSION or preset.payload != payload:
                continue
            if any(
                _same_association_target(candidate, association)
                for candidate in preset.associations
            ):
                return preset
            updated = replace(
                preset,
                associations=(*preset.associations, association),
                updated_at=self._clock(),
            )
            presets[index] = updated
            self._repository.save_presets(tuple(presets))
            return updated

        timestamp = self._clock()
        preset = UserPreset(
            id=self._new_id(UserPresetKind.DIMENSION),
            kind=UserPresetKind.DIMENSION,
            label=_default_dimension_label(payload),
            payload=payload,
            associations=(association,),
            created_at=timestamp,
            updated_at=timestamp,
        )
        presets.append(preset)
        self._repository.save_presets(tuple(presets))
        return preset

    def list_node_input_presets(
        self,
        *,
        node_type: str,
        associations: tuple[UserPresetAssociation, ...],
    ) -> NodeInputPresetListing:
        """Return node input presets for one node type and matching associations."""

        presets = _sorted_node_input_presets(
            self._repository.load_presets(),
            node_type=node_type,
        )
        sections: list[NodeInputPresetSection] = []
        shown_preset_ids: set[str] = set()
        for association in associations:
            matching_presets = tuple(
                preset
                for preset in presets
                if preset.id not in shown_preset_ids
                and any(
                    _same_association_target(candidate, association)
                    for candidate in preset.associations
                )
            )
            if not matching_presets:
                continue
            shown_preset_ids.update(preset.id for preset in matching_presets)
            sections.append(
                NodeInputPresetSection(
                    association=association,
                    presets=matching_presets,
                )
            )
        return NodeInputPresetListing(sections=tuple(sections))

    def save_node_input_preset(
        self,
        *,
        label: str,
        node_type: str,
        inputs: JsonObject,
        association: UserPresetAssociation,
    ) -> UserPreset:
        """Create or update a named node input preset for one node type and scope."""

        stripped_label = label.strip()
        if not stripped_label:
            raise ValueError("Node input preset label must be non-empty")
        payload = NodeInputPresetPayload(node_type=node_type, inputs=inputs)
        presets = list(self._repository.load_presets())
        for index, preset in enumerate(presets):
            if not _same_node_input_preset_target(
                preset,
                label=stripped_label,
                payload=payload,
                association=association,
            ):
                continue
            updated = replace(
                preset,
                label=stripped_label,
                payload=payload,
                updated_at=self._clock(),
            )
            presets[index] = updated
            self._repository.save_presets(tuple(presets))
            return updated

        timestamp = self._clock()
        preset = UserPreset(
            id=self._new_id(UserPresetKind.NODE_INPUTS),
            kind=UserPresetKind.NODE_INPUTS,
            label=stripped_label,
            payload=payload,
            associations=(association,),
            created_at=timestamp,
            updated_at=timestamp,
        )
        presets.append(preset)
        self._repository.save_presets(tuple(presets))
        return preset

    def list_prompt_string_presets(
        self,
        associations: tuple[UserPresetAssociation, ...],
    ) -> PromptStringPresetListing:
        """Return prompt string presets grouped by matching associations."""

        presets = _sorted_prompt_string_presets(self._repository.load_presets())
        sections: list[PromptStringPresetSection] = []
        shown_preset_ids: set[str] = set()
        for association in associations:
            matching_presets = tuple(
                preset
                for preset in presets
                if preset.id not in shown_preset_ids
                and any(
                    _same_association_target(candidate, association)
                    for candidate in preset.associations
                )
            )
            if not matching_presets:
                continue
            shown_preset_ids.update(preset.id for preset in matching_presets)
            sections.append(
                PromptStringPresetSection(
                    title=association.label,
                    association=association,
                    presets=matching_presets,
                )
            )
        return PromptStringPresetListing(sections=tuple(sections))

    def save_prompt_string_preset(
        self,
        *,
        label: str,
        text: str,
        association: UserPresetAssociation,
    ) -> UserPreset:
        """Create or update a prompt string preset for one association."""

        stripped_label = label.strip()
        if not stripped_label:
            raise ValueError("Prompt string preset label must be non-empty")
        payload = PromptStringPresetPayload(text=text)
        presets = list(self._repository.load_presets())
        for index, preset in enumerate(presets):
            if (
                preset.kind is not UserPresetKind.PROMPT_STRING
                or preset.payload != payload
            ):
                continue
            updated_associations = preset.associations
            if not any(
                _same_association_target(candidate, association)
                for candidate in preset.associations
            ):
                updated_associations = (*preset.associations, association)
            updated = replace(
                preset,
                label=stripped_label,
                associations=updated_associations,
                updated_at=self._clock(),
            )
            presets[index] = updated
            self._repository.save_presets(tuple(presets))
            return updated

        timestamp = self._clock()
        preset = UserPreset(
            id=self._new_id(UserPresetKind.PROMPT_STRING),
            kind=UserPresetKind.PROMPT_STRING,
            label=stripped_label,
            payload=payload,
            associations=(association,),
            created_at=timestamp,
            updated_at=timestamp,
        )
        presets.append(preset)
        self._repository.save_presets(tuple(presets))
        return preset

    def _new_id(self, kind: UserPresetKind) -> str:
        """Return a new id using the test hook or a kind-specific production prefix."""

        if self._id_factory is not None:
            return self._id_factory()
        return _new_preset_id(kind)


def _sorted_dimension_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[UserPreset, ...]:
    """Return dimension presets in deterministic presentation order."""

    return tuple(
        sorted(
            (preset for preset in presets if preset.kind is UserPresetKind.DIMENSION),
            key=lambda preset: (
                cast(DimensionPresetPayload, preset.payload).short_edge,
                cast(DimensionPresetPayload, preset.payload).long_edge,
                preset.label.casefold(),
                preset.id,
            ),
        )
    )


def _sorted_prompt_string_presets(
    presets: tuple[UserPreset, ...],
) -> tuple[UserPreset, ...]:
    """Return prompt string presets in deterministic presentation order."""

    return tuple(
        sorted(
            (
                preset
                for preset in presets
                if preset.kind is UserPresetKind.PROMPT_STRING
                and isinstance(preset.payload, PromptStringPresetPayload)
            ),
            key=lambda preset: (
                preset.label.casefold(),
                preset.payload.text.casefold()
                if isinstance(preset.payload, PromptStringPresetPayload)
                else "",
                preset.id,
            ),
        )
    )


def _sorted_node_input_presets(
    presets: tuple[UserPreset, ...],
    *,
    node_type: str,
) -> tuple[UserPreset, ...]:
    """Return node input presets for one node type in presentation order."""

    return tuple(
        sorted(
            (
                preset
                for preset in presets
                if preset.kind is UserPresetKind.NODE_INPUTS
                and isinstance(preset.payload, NodeInputPresetPayload)
                and preset.payload.node_type == node_type
            ),
            key=lambda preset: (
                preset.label.casefold(),
                preset.id,
            ),
        )
    )


def _has_global_association(preset: UserPreset) -> bool:
    """Return whether one preset is available globally."""

    return any(
        association.scope is UserPresetAssociationScope.GLOBAL
        for association in preset.associations
    )


def _same_association_target(
    left: UserPresetAssociation,
    right: UserPresetAssociation,
) -> bool:
    """Return whether two associations address the same preset context."""

    return (
        left.scope is right.scope
        and left.provider == right.provider
        and left.key == right.key
    )


def _same_node_input_preset_target(
    preset: UserPreset,
    *,
    label: str,
    payload: NodeInputPresetPayload,
    association: UserPresetAssociation,
) -> bool:
    """Return whether a preset is the named node-scope record to update."""

    return (
        preset.kind is UserPresetKind.NODE_INPUTS
        and isinstance(preset.payload, NodeInputPresetPayload)
        and preset.payload.node_type == payload.node_type
        and preset.label.casefold() == label.casefold()
        and any(
            _same_association_target(candidate, association)
            for candidate in preset.associations
        )
    )


def _default_dimension_label(payload: DimensionPresetPayload) -> str:
    """Return the default label for one canonical dimension payload."""

    return f"{payload.short_edge} x {payload.long_edge}"


def _new_preset_id(kind: UserPresetKind) -> str:
    """Return a new stable user preset id for one preset kind."""

    return f"{kind.value}:{uuid4().hex}"


def _utc_now_iso() -> str:
    """Return a UTC timestamp string for preset updates."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


__all__ = [
    "DimensionPresetListing",
    "DimensionPresetSection",
    "NodeInputPresetListing",
    "NodeInputPresetSection",
    "PromptStringPresetListing",
    "PromptStringPresetSection",
    "UserPresetRepository",
    "UserPresetService",
]
