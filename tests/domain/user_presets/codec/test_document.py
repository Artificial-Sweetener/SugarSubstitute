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

"""Contract tests for user preset JSON codecs."""

from __future__ import annotations

from substitute.domain.user_presets import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
    canonical_dimension_payload,
    decode_user_presets_document,
    encode_user_presets_document,
)


def test_dimension_preset_encodes_and_decodes() -> None:
    """A valid dimension preset should round-trip through versioned JSON."""

    preset = _dimension_preset(
        associations=(
            GLOBAL_PRESET_ASSOCIATION,
            _family_association("illustrious", "Illustrious"),
        )
    )

    decoded = decode_user_presets_document(encode_user_presets_document((preset,)))

    assert decoded == (preset,)


def test_prompt_string_preset_encodes_and_decodes() -> None:
    """A valid prompt string preset should round-trip through versioned JSON."""

    preset = UserPreset(
        id="prompt:test",
        kind=UserPresetKind.PROMPT_STRING,
        label="Blue eyes",
        payload=PromptStringPresetPayload(text="blue eyes"),
        associations=(GLOBAL_PRESET_ASSOCIATION,),
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )

    decoded = decode_user_presets_document(encode_user_presets_document((preset,)))

    assert decoded == (preset,)


def test_node_input_preset_encodes_and_decodes() -> None:
    """A valid node input preset should round-trip through versioned JSON."""

    preset = _node_input_preset(associations=(GLOBAL_PRESET_ASSOCIATION,))

    decoded = decode_user_presets_document(encode_user_presets_document((preset,)))

    assert decoded == (preset,)


def test_mixed_user_presets_decode() -> None:
    """The shared preset file should support every preset kind together."""

    dimension = _dimension_preset(associations=(GLOBAL_PRESET_ASSOCIATION,))
    node_inputs = _node_input_preset(associations=(GLOBAL_PRESET_ASSOCIATION,))
    prompt = UserPreset(
        id="prompt:test",
        kind=UserPresetKind.PROMPT_STRING,
        label="Blue eyes",
        payload=PromptStringPresetPayload(text="blue eyes"),
        associations=(GLOBAL_PRESET_ASSOCIATION,),
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )

    decoded = decode_user_presets_document(
        encode_user_presets_document((dimension, node_inputs, prompt))
    )

    assert decoded == (dimension, node_inputs, prompt)


def test_invalid_dimension_payload_is_skipped() -> None:
    """Non-positive dimension payloads should not decode as presets."""

    decoded = decode_user_presets_document(
        {
            "version": 1,
            "presets": [
                {
                    "id": "dimension:bad",
                    "kind": "dimension",
                    "label": "Bad",
                    "payload": {"short_edge": 0, "long_edge": 1024},
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                }
            ],
        }
    )

    assert decoded == ()


def test_invalid_prompt_string_payload_is_skipped() -> None:
    """Blank prompt text should not decode as a prompt string preset."""

    decoded = decode_user_presets_document(
        {
            "version": 1,
            "presets": [
                {
                    "id": "prompt:bad",
                    "kind": "prompt_string",
                    "label": "Bad",
                    "payload": {"text": "   "},
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                }
            ],
        }
    )

    assert decoded == ()


def test_invalid_node_input_payload_is_skipped() -> None:
    """Invalid node input payloads should not decode as presets."""

    decoded = decode_user_presets_document(
        {
            "version": 1,
            "presets": [
                {
                    "id": "node_inputs:blank-node",
                    "kind": "node_inputs",
                    "label": "Bad",
                    "payload": {"node_type": " ", "inputs": {"steps": 20}},
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                },
                {
                    "id": "node_inputs:empty-inputs",
                    "kind": "node_inputs",
                    "label": "Bad",
                    "payload": {"node_type": "KSampler", "inputs": {}},
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                },
                {
                    "id": "node_inputs:connection",
                    "kind": "node_inputs",
                    "label": "Bad",
                    "payload": {
                        "node_type": "KSampler",
                        "inputs": {"model": ["checkpoint", 0]},
                    },
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                },
            ],
        }
    )

    assert decoded == ()


def test_unknown_kind_and_scope_are_skipped() -> None:
    """Unknown preset kinds and association scopes should not decode."""

    decoded = decode_user_presets_document(
        {
            "version": 1,
            "presets": [
                {
                    "id": "prompt:future",
                    "kind": "future_kind",
                    "label": "Future",
                    "payload": {"short_edge": 512, "long_edge": 768},
                    "associations": [],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                },
                {
                    "id": "dimension:known",
                    "kind": "dimension",
                    "label": "Known",
                    "payload": {"short_edge": 512, "long_edge": 768},
                    "associations": [
                        {
                            "scope": "future_scope",
                            "provider": "future",
                            "key": "future",
                            "label": "Future",
                        },
                        {
                            "scope": "global",
                            "provider": None,
                            "key": "global",
                            "label": "Global",
                        },
                    ],
                    "created_at": "2026-04-20T12:00:00Z",
                    "updated_at": "2026-04-20T12:00:00Z",
                },
            ],
        }
    )

    assert len(decoded) == 1
    assert decoded[0].associations == (GLOBAL_PRESET_ASSOCIATION,)


def test_canonical_dimension_payload_uses_short_and_long_edges() -> None:
    """Dimension canonicalization should ignore orientation."""

    assert canonical_dimension_payload(1536, 1024) == DimensionPresetPayload(
        short_edge=1024,
        long_edge=1536,
    )


def _dimension_preset(
    *,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic dimension preset for codec tests."""

    return UserPreset(
        id="dimension:test",
        kind=UserPresetKind.DIMENSION,
        label="1024 x 1536",
        payload=DimensionPresetPayload(short_edge=1024, long_edge=1536),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _node_input_preset(
    *,
    associations: tuple[UserPresetAssociation, ...],
) -> UserPreset:
    """Return one deterministic node input preset for codec tests."""

    return UserPreset(
        id="node_inputs:test",
        kind=UserPresetKind.NODE_INPUTS,
        label="Fast Draft",
        payload=NodeInputPresetPayload(
            node_type="KSampler",
            inputs={"steps": 20, "cfg": 7.0, "enabled": True},
        ),
        associations=associations,
        created_at="2026-04-20T12:00:00Z",
        updated_at="2026-04-20T12:00:00Z",
    )


def _family_association(key: str, label: str) -> UserPresetAssociation:
    """Return one CivitAI model-family preset association."""

    return UserPresetAssociation(
        scope=UserPresetAssociationScope.MODEL_FAMILY,
        provider="civitai",
        key=key,
        label=label,
    )
