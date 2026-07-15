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

"""Encode and decode versioned user preset JSON payloads."""

from __future__ import annotations

from typing import cast

from substitute.domain.common import JsonObject
from substitute.domain.user_presets.models import (
    DimensionPresetPayload,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
    UserPresetPayload,
)

USER_PRESETS_SCHEMA_VERSION = 1


def encode_user_presets_document(
    presets: tuple[UserPreset, ...],
) -> JsonObject:
    """Return a versioned JSON document for user preset storage."""

    return {
        "version": USER_PRESETS_SCHEMA_VERSION,
        "presets": [encode_user_preset(preset) for preset in presets],
    }


def decode_user_presets_document(payload: JsonObject) -> tuple[UserPreset, ...]:
    """Return valid user presets decoded from a versioned JSON document."""

    if payload.get("version") != USER_PRESETS_SCHEMA_VERSION:
        return ()
    raw_presets = payload.get("presets")
    if not isinstance(raw_presets, list):
        return ()
    presets: list[UserPreset] = []
    for raw_preset in raw_presets:
        if not isinstance(raw_preset, dict):
            continue
        preset = decode_user_preset(cast(JsonObject, raw_preset))
        if preset is not None:
            presets.append(preset)
    return tuple(presets)


def encode_user_preset(preset: UserPreset) -> JsonObject:
    """Return one user preset as a stable JSON object."""

    return {
        "id": preset.id,
        "kind": preset.kind.value,
        "label": preset.label,
        "payload": encode_user_preset_payload(preset.kind, preset.payload),
        "associations": [
            encode_user_preset_association(association)
            for association in preset.associations
        ],
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


def decode_user_preset(payload: JsonObject) -> UserPreset | None:
    """Return one decoded user preset, or ``None`` when invalid."""

    raw_kind = payload.get("kind")
    if not isinstance(raw_kind, str):
        return None
    try:
        kind = UserPresetKind(raw_kind)
    except ValueError:
        return None

    raw_id = payload.get("id")
    raw_label = payload.get("label")
    raw_payload = payload.get("payload")
    raw_created_at = payload.get("created_at")
    raw_updated_at = payload.get("updated_at")
    if (
        not isinstance(raw_id, str)
        or not isinstance(raw_label, str)
        or not isinstance(raw_payload, dict)
        or not isinstance(raw_created_at, str)
        or not isinstance(raw_updated_at, str)
    ):
        return None

    preset_payload = decode_user_preset_payload(kind, cast(JsonObject, raw_payload))
    if preset_payload is None:
        return None

    associations = _decode_user_preset_associations(payload.get("associations"))
    try:
        return UserPreset(
            id=raw_id,
            kind=kind,
            label=raw_label,
            payload=preset_payload,
            associations=associations,
            created_at=raw_created_at,
            updated_at=raw_updated_at,
        )
    except ValueError:
        return None


def encode_user_preset_payload(
    kind: UserPresetKind,
    payload: UserPresetPayload,
) -> JsonObject:
    """Return one typed preset payload as JSON."""

    if kind is UserPresetKind.DIMENSION and isinstance(
        payload,
        DimensionPresetPayload,
    ):
        return encode_dimension_preset_payload(payload)
    if kind is UserPresetKind.NODE_INPUTS and isinstance(
        payload,
        NodeInputPresetPayload,
    ):
        return encode_node_input_preset_payload(payload)
    if kind is UserPresetKind.PROMPT_STRING and isinstance(
        payload,
        PromptStringPresetPayload,
    ):
        return encode_prompt_string_preset_payload(payload)
    raise ValueError("Preset kind does not match payload type")


def decode_user_preset_payload(
    kind: UserPresetKind,
    payload: JsonObject,
) -> UserPresetPayload | None:
    """Return a typed preset payload decoded from JSON."""

    if kind is UserPresetKind.DIMENSION:
        return decode_dimension_preset_payload(payload)
    if kind is UserPresetKind.NODE_INPUTS:
        return decode_node_input_preset_payload(payload)
    if kind is UserPresetKind.PROMPT_STRING:
        return decode_prompt_string_preset_payload(payload)
    return None


def encode_dimension_preset_payload(payload: DimensionPresetPayload) -> JsonObject:
    """Return one dimension preset payload as JSON."""

    return {
        "short_edge": payload.short_edge,
        "long_edge": payload.long_edge,
    }


def decode_dimension_preset_payload(
    payload: JsonObject,
) -> DimensionPresetPayload | None:
    """Return a dimension payload decoded from JSON, or ``None`` when invalid."""

    short_edge = payload.get("short_edge")
    long_edge = payload.get("long_edge")
    if (
        not isinstance(short_edge, int)
        or isinstance(short_edge, bool)
        or not isinstance(long_edge, int)
        or isinstance(long_edge, bool)
    ):
        return None
    try:
        return DimensionPresetPayload(short_edge=short_edge, long_edge=long_edge)
    except ValueError:
        return None


def encode_node_input_preset_payload(payload: NodeInputPresetPayload) -> JsonObject:
    """Return one node input preset payload as JSON."""

    return {
        "node_type": payload.node_type,
        "inputs": dict(payload.inputs),
    }


def decode_node_input_preset_payload(
    payload: JsonObject,
) -> NodeInputPresetPayload | None:
    """Return a node input payload decoded from JSON, or ``None`` when invalid."""

    node_type = payload.get("node_type")
    inputs = payload.get("inputs")
    if not isinstance(node_type, str) or not isinstance(inputs, dict):
        return None
    try:
        return NodeInputPresetPayload(
            node_type=node_type,
            inputs=cast(JsonObject, inputs),
        )
    except ValueError:
        return None


def encode_prompt_string_preset_payload(
    payload: PromptStringPresetPayload,
) -> JsonObject:
    """Return one prompt string preset payload as JSON."""

    return {"text": payload.text}


def decode_prompt_string_preset_payload(
    payload: JsonObject,
) -> PromptStringPresetPayload | None:
    """Return a prompt string payload decoded from JSON, or ``None`` when invalid."""

    text = payload.get("text")
    if not isinstance(text, str):
        return None
    try:
        return PromptStringPresetPayload(text=text)
    except ValueError:
        return None


def encode_user_preset_association(
    association: UserPresetAssociation,
) -> JsonObject:
    """Return one preset association as JSON."""

    return {
        "scope": association.scope.value,
        "provider": association.provider,
        "key": association.key,
        "label": association.label,
    }


def decode_user_preset_association(
    payload: JsonObject,
) -> UserPresetAssociation | None:
    """Return a preset association decoded from JSON, or ``None`` when invalid."""

    raw_scope = payload.get("scope")
    if not isinstance(raw_scope, str):
        return None
    try:
        scope = UserPresetAssociationScope(raw_scope)
    except ValueError:
        return None
    raw_provider = payload.get("provider")
    raw_key = payload.get("key")
    raw_label = payload.get("label")
    if raw_provider is not None and not isinstance(raw_provider, str):
        return None
    if not isinstance(raw_key, str) or not isinstance(raw_label, str):
        return None
    try:
        return UserPresetAssociation(
            scope=scope,
            provider=raw_provider,
            key=raw_key,
            label=raw_label,
        )
    except ValueError:
        return None


def _decode_user_preset_associations(
    value: object,
) -> tuple[UserPresetAssociation, ...]:
    """Return valid associations decoded from a JSON value."""

    if not isinstance(value, list):
        return ()
    associations: list[UserPresetAssociation] = []
    for raw_association in value:
        if not isinstance(raw_association, dict):
            continue
        association = decode_user_preset_association(cast(JsonObject, raw_association))
        if association is not None:
            associations.append(association)
    return tuple(associations)


__all__ = [
    "USER_PRESETS_SCHEMA_VERSION",
    "decode_dimension_preset_payload",
    "decode_node_input_preset_payload",
    "decode_prompt_string_preset_payload",
    "decode_user_preset",
    "decode_user_preset_association",
    "decode_user_preset_payload",
    "decode_user_presets_document",
    "encode_dimension_preset_payload",
    "encode_node_input_preset_payload",
    "encode_prompt_string_preset_payload",
    "encode_user_preset",
    "encode_user_preset_association",
    "encode_user_preset_payload",
    "encode_user_presets_document",
]
