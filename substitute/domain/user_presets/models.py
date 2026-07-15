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

"""Define durable user preset records and association targets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from substitute.domain.common import JsonObject, JsonValue


class UserPresetKind(StrEnum):
    """Identify the payload category for one user preset."""

    DIMENSION = "dimension"
    NODE_INPUTS = "node_inputs"
    PROMPT_STRING = "prompt_string"


class UserPresetAssociationScope(StrEnum):
    """Describe where a user preset should be offered."""

    GLOBAL = "global"
    MODEL_FAMILY = "model_family"
    PROVIDER_MODEL = "provider_model"
    PROVIDER_MODEL_VERSION = "provider_model_version"
    LOCAL_MODEL = "local_model"


@dataclass(frozen=True)
class DimensionPresetPayload:
    """Store one canonical dimension shape independent of orientation."""

    short_edge: int
    long_edge: int

    def __post_init__(self) -> None:
        """Validate that the shape is positive and canonical."""

        if self.short_edge <= 0 or self.long_edge <= 0:
            raise ValueError("Dimension preset edges must be positive")
        if self.short_edge > self.long_edge:
            raise ValueError("Dimension preset edges must be canonical")


@dataclass(frozen=True)
class PromptStringPresetPayload:
    """Store prompt text saved for later insertion."""

    text: str

    def __post_init__(self) -> None:
        """Validate that the saved prompt text has meaningful content."""

        if not self.text.strip():
            raise ValueError("Prompt string preset text must be non-empty")


@dataclass(frozen=True)
class NodeInputPresetPayload:
    """Store editable input values for one Comfy node class."""

    node_type: str
    inputs: JsonObject

    def __post_init__(self) -> None:
        """Validate node identity and detach stored JSON-safe input values."""

        if not self.node_type.strip():
            raise ValueError("Node input preset node type must be non-empty")
        if not self.inputs:
            raise ValueError("Node input preset inputs must be non-empty")
        copied_inputs = _copy_json_object(self.inputs)
        object.__setattr__(self, "inputs", copied_inputs)


UserPresetPayload = (
    DimensionPresetPayload | NodeInputPresetPayload | PromptStringPresetPayload
)


@dataclass(frozen=True)
class UserPresetAssociation:
    """Describe one global or model-related place a preset applies."""

    scope: UserPresetAssociationScope
    provider: str | None
    key: str
    label: str

    def __post_init__(self) -> None:
        """Validate association identity fields."""

        if not self.key.strip():
            raise ValueError("User preset association key must be non-empty")
        if not self.label.strip():
            raise ValueError("User preset association label must be non-empty")
        if self.scope is UserPresetAssociationScope.GLOBAL and (
            self.provider is not None or self.key != "global"
        ):
            raise ValueError("Global preset associations must use the global key")
        if self.scope is not UserPresetAssociationScope.GLOBAL and not (
            self.provider and self.provider.strip()
        ):
            raise ValueError("Model preset associations must include a provider")


@dataclass(frozen=True)
class UserPreset:
    """Store one user-created preset and the contexts where it applies."""

    id: str
    kind: UserPresetKind
    label: str
    payload: UserPresetPayload
    associations: tuple[UserPresetAssociation, ...]
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        """Validate stable preset identity and presentation fields."""

        if not self.id.strip():
            raise ValueError("User preset id must be non-empty")
        if not self.label.strip():
            raise ValueError("User preset label must be non-empty")
        if not self.created_at.strip() or not self.updated_at.strip():
            raise ValueError("User preset timestamps must be non-empty")


GLOBAL_PRESET_ASSOCIATION = UserPresetAssociation(
    scope=UserPresetAssociationScope.GLOBAL,
    provider=None,
    key="global",
    label="Global",
)


def canonical_dimension_payload(width: int, height: int) -> DimensionPresetPayload:
    """Return a canonical dimension payload from oriented width and height."""

    return DimensionPresetPayload(
        short_edge=min(width, height),
        long_edge=max(width, height),
    )


def _copy_json_object(value: JsonObject) -> JsonObject:
    """Return a detached JSON object after validating preset-safe content."""

    copied: JsonObject = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Node input preset keys must be non-empty strings")
        copied[key] = _copy_json_value(item)
    return copied


def _copy_json_value(value: JsonValue) -> JsonValue:
    """Return a detached JSON value suitable for node input preset storage."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, tuple):
        raise ValueError("Node input preset values must be JSON-safe")
    if isinstance(value, list):
        if _is_graph_connection_value(value):
            raise ValueError("Node input preset values must not be graph connections")
        return [_copy_json_value(item) for item in value]
    if isinstance(value, dict):
        return _copy_json_object(value)
    raise ValueError("Node input preset values must be JSON-safe")


def _is_graph_connection_value(value: list[object]) -> bool:
    """Return whether a list has Comfy's common graph-connection shape."""

    return len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


__all__ = [
    "DimensionPresetPayload",
    "GLOBAL_PRESET_ASSOCIATION",
    "NodeInputPresetPayload",
    "PromptStringPresetPayload",
    "UserPreset",
    "UserPresetAssociation",
    "UserPresetAssociationScope",
    "UserPresetKind",
    "UserPresetPayload",
    "canonical_dimension_payload",
]
