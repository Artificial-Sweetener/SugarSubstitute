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

"""Expose domain models and codecs for user-created presets."""

from __future__ import annotations

from substitute.domain.user_presets.codec import (
    USER_PRESETS_SCHEMA_VERSION,
    decode_dimension_preset_payload,
    decode_node_input_preset_payload,
    decode_prompt_string_preset_payload,
    decode_user_preset,
    decode_user_preset_association,
    decode_user_preset_payload,
    decode_user_presets_document,
    encode_dimension_preset_payload,
    encode_node_input_preset_payload,
    encode_prompt_string_preset_payload,
    encode_user_preset,
    encode_user_preset_association,
    encode_user_preset_payload,
    encode_user_presets_document,
)
from substitute.domain.user_presets.models import (
    DimensionPresetPayload,
    GLOBAL_PRESET_ASSOCIATION,
    NodeInputPresetPayload,
    PromptStringPresetPayload,
    UserPreset,
    UserPresetAssociation,
    UserPresetAssociationScope,
    UserPresetKind,
    UserPresetPayload,
    canonical_dimension_payload,
)

__all__ = [
    "DimensionPresetPayload",
    "GLOBAL_PRESET_ASSOCIATION",
    "NodeInputPresetPayload",
    "PromptStringPresetPayload",
    "USER_PRESETS_SCHEMA_VERSION",
    "UserPreset",
    "UserPresetAssociation",
    "UserPresetAssociationScope",
    "UserPresetKind",
    "UserPresetPayload",
    "canonical_dimension_payload",
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
