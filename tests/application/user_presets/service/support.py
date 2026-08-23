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

"""Contract tests for user preset application service behavior."""

from __future__ import annotations

from substitute.application.user_presets import UserPresetService
from substitute.domain.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
)

__all__ = [
    "DimensionPresetPayload",
    "GLOBAL_PRESET_ASSOCIATION",
    "NodeInputPresetPayload",
    "PromptStringPresetPayload",
    "UserPresetKind",
    "UserPresetService",
    "_MemoryRepository",
    "_checkpoint",
    "_family",
    "_node_preset",
    "_preset",
    "_prompt_preset",
    "_service",
]


class _MemoryRepository:
    """Store user presets in memory for service tests."""

    def __init__(self, presets: tuple[UserPreset, ...] = ()) -> None:
        """Initialize stored presets."""

        self.presets = presets
        self.save_calls: list[tuple[UserPreset, ...]] = []

    def load_presets(self) -> tuple[UserPreset, ...]:
        """Return stored presets."""

        return self.presets

    def save_presets(self, presets: tuple[UserPreset, ...]) -> None:
        """Persist presets in memory and record the call."""

        self.presets = presets
        self.save_calls.append(presets)


def _service(repository: _MemoryRepository) -> UserPresetService:
    """Return a deterministic user preset service."""

    ids = iter(
        (
            "preset:test-1",
            "preset:test-2",
            "preset:test-3",
            "preset:test-4",
        )
    )
    return UserPresetService(
        repository,
        id_factory=lambda: next(ids),
        clock=lambda: "2026-04-20T12:00:00Z",
    )


def _family(key: str, label: str) -> UserPresetAssociation:
    """Return one model-family association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.MODEL_FAMILY,
        provider="civitai",
        key=key,
        label=label,
    )


def _checkpoint(key: str, label: str) -> UserPresetAssociation:
    """Return one CivitAI model-version association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.PROVIDER_MODEL_VERSION,
        provider="civitai",
        key=key,
        label=label,
    )


def _preset(
    preset_id: str,
    *,
    short_edge: int,
    long_edge: int,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic dimension preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.DIMENSION,
        label=f"{short_edge} x {long_edge}",
        payload=DimensionPresetPayload(short_edge=short_edge, long_edge=long_edge),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _node_preset(
    preset_id: str,
    *,
    label: str,
    node_type: str,
    inputs: dict[str, object],
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic node input preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.NODE_INPUTS,
        label=label,
        payload=NodeInputPresetPayload(node_type=node_type, inputs=inputs),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _prompt_preset(
    preset_id: str,
    *,
    label: str,
    text: str,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic prompt string preset."""

    return UserPreset(
        id=preset_id,
        kind=UserPresetKind.PROMPT_STRING,
        label=label,
        payload=PromptStringPresetPayload(text=text),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )
