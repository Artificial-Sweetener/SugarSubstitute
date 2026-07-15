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

"""Detect model-selection nodes without touching model catalog caches."""

from __future__ import annotations

from collections.abc import Mapping

from .list_value_resolver import extract_live_list_options

_MODEL_FIELD_KEYS = frozenset(
    {
        ("CheckpointLoaderSimple", "ckpt_name"),
        ("VAELoader", "vae_name"),
        ("LoraLoader", "lora_name"),
        ("LoraLoaderModelOnly", "lora_name"),
        ("UpscaleModelLoader", "model_name"),
        ("UNETLoader", "unet_name"),
        ("DualCLIPLoader", "clip_name1"),
        ("DualCLIPLoader", "clip_name2"),
        ("CLIPLoader", "clip_name"),
        ("ControlNetLoader", "control_net_name"),
    }
)
_MODEL_FIELD_KEY_FRAGMENTS = (
    "ckpt",
    "checkpoint",
    "lora",
    "vae",
    "unet",
    "diffusion",
    "clip",
    "controlnet",
    "control_net",
)
_MODEL_CLASS_FRAGMENTS = (
    "loader",
    "checkpoint",
    "lora",
    "vae",
    "unet",
    "diffusion",
    "clip",
    "controlnet",
    "control_net",
    "upscale",
)


class ModelBackedNodeDetector:
    """Detect nodes that expose model-selection fields without catalog reads."""

    def __init__(self, **_ignored: object) -> None:
        """Accept legacy composition arguments while keeping detection cache-neutral."""

    def node_uses_configured_model(
        self,
        *,
        node_data: Mapping[str, object],
        live_definition: Mapping[str, object] | None,
    ) -> bool:
        """Return whether node metadata exposes a model-selection literal field."""

        class_type = node_data.get("class_type")
        if not isinstance(class_type, str):
            return False
        return any(
            _field_looks_model_backed(class_type, field_key, field_info)
            for field_key, field_info in _definition_fields(live_definition).items()
        )


def _definition_fields(
    live_definition: Mapping[str, object] | None,
) -> dict[str, object]:
    """Return all input definition fields keyed by field name."""

    if not isinstance(live_definition, Mapping):
        return {}
    input_section = live_definition.get("input")
    if not isinstance(input_section, Mapping):
        return {}

    fields: dict[str, object] = {}
    for section_name in ("required", "optional"):
        section = input_section.get(section_name)
        if not isinstance(section, Mapping):
            continue
        fields.update(
            (key, value) for key, value in section.items() if isinstance(key, str)
        )
    return fields


def _field_looks_model_backed(
    class_type: str,
    field_key: str,
    field_info: object,
) -> bool:
    """Return whether one finite-choice field looks like a model selector."""

    if not extract_live_list_options(field_info):
        return False
    if (class_type, field_key) in _MODEL_FIELD_KEYS:
        return True
    normalized_field = field_key.strip().casefold()
    if any(fragment in normalized_field for fragment in _MODEL_FIELD_KEY_FRAGMENTS):
        return True
    normalized_class = class_type.strip().casefold()
    return normalized_field in {"model", "model_name"} and any(
        fragment in normalized_class for fragment in _MODEL_CLASS_FRAGMENTS
    )


__all__ = ["ModelBackedNodeDetector"]
