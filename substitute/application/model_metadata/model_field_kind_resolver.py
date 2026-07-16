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

"""Resolve model catalog kinds from typed Comfy node input identities."""

from __future__ import annotations

_EXACT_MODEL_FIELDS = {
    ("CheckpointLoaderSimple", "ckpt_name"): "checkpoints",
    ("SimpleSyrup.SimpleLoadCheckpoint", "ckpt_name"): "checkpoints",
    ("LoraLoader", "lora_name"): "loras",
    ("LoraLoaderModelOnly", "lora_name"): "loras",
    ("VAELoader", "vae_name"): "vae",
    ("UNETLoader", "unet_name"): "diffusion_models",
    ("SimpleSyrup.SimpleLoadAnima", "diffusion_model"): "diffusion_models",
    ("UpscaleModelLoader", "model_name"): "upscale_models",
    ("ControlNetLoader", "control_net_name"): "controlnet",
    ("CLIPLoader", "clip_name"): "text_encoders",
    ("DualCLIPLoader", "clip_name1"): "text_encoders",
    ("DualCLIPLoader", "clip_name2"): "text_encoders",
    ("Power Lora Loader (rgthree)", "lora"): "loras",
}

_UNQUALIFIED_MODEL_FIELDS = {
    "ckpt_name": "checkpoints",
    "checkpoint": "checkpoints",
    "checkpoint_name": "checkpoints",
    "lora_name": "loras",
    "vae_name": "vae",
    "unet_name": "diffusion_models",
    "diffusion_model": "diffusion_models",
    "control_net_name": "controlnet",
    "clip_name": "text_encoders",
    "clip_name1": "text_encoders",
    "clip_name2": "text_encoders",
}


def model_kind_for_field(*, class_type: str, input_key: str) -> str | None:
    """Return the model catalog kind for one recognized model-picker field."""

    normalized_class_type = class_type.strip()
    normalized_input_key = input_key.strip()
    exact_kind = _EXACT_MODEL_FIELDS.get((normalized_class_type, normalized_input_key))
    if exact_kind is not None:
        return exact_kind
    unqualified_kind = _UNQUALIFIED_MODEL_FIELDS.get(normalized_input_key)
    if unqualified_kind is not None:
        return unqualified_kind
    normalized_key = normalized_input_key.casefold()
    if "checkpoint" in normalized_key or "ckpt" in normalized_key:
        return "checkpoints"
    if "lora" in normalized_key:
        return "loras"
    if "unet" in normalized_key or "diffusion" in normalized_key:
        return "diffusion_models"
    if "controlnet" in normalized_key or "control_net" in normalized_key:
        return "controlnet"
    if "clip" in normalized_key or "text_encoder" in normalized_key:
        return "text_encoders"
    return None


__all__ = ["model_kind_for_field"]
