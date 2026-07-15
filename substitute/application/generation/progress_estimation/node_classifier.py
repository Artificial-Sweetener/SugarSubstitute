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

"""Classify Comfy nodes into progress-estimation roles."""

from __future__ import annotations

from typing import Any, Literal, Mapping

NodeCategory = Literal["loader", "sampler", "output", "ordinary"]

_LOADER_CLASS_MARKERS = (
    "checkpointloader",
    "unetloader",
    "diffusionmodelload",
    "cliploader",
    "vaeloader",
    "loraloader",
    "controlnetloader",
    "ipadaptermodelloader",
    "photomakerloader",
    "stylemodelload",
    "loadcheckpoint",
    "loadunet",
    "loadclip",
    "loadvae",
    "loadlora",
)
_LOADER_INPUT_NAMES = (
    "ckpt_name",
    "unet_name",
    "diffusion_model_name",
    "clip_name",
    "clip_name1",
    "clip_name2",
    "vae_name",
    "lora_name",
    "control_net_name",
    "ipadapter_file",
    "model_name",
)
_SAMPLER_INPUT_NAMES = (
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "noise_seed",
    "seed",
)


def classify_node(node_data: Mapping[str, Any]) -> NodeCategory:
    """Return the progress-estimation category for one Comfy prompt node.

    Loader detection is deliberately narrower than simple substring matching:
    nodes such as ``CLIPTextEncode`` and ``VAEDecode`` mention model concepts
    but perform workflow work and must remain in the main workflow estimate.
    """

    class_type = str(node_data.get("class_type") or "").lower()
    inputs = node_data.get("inputs")
    input_names = (
        tuple(str(name).lower() for name in inputs) if isinstance(inputs, dict) else ()
    )

    if _is_loader(class_type, input_names):
        return "loader"
    if _is_sampler(class_type, input_names):
        return "sampler"
    if _is_output(class_type):
        return "output"
    return "ordinary"


def _is_loader(class_type: str, input_names: tuple[str, ...]) -> bool:
    """Return whether node metadata identifies model-loading work."""

    if any(marker in class_type for marker in _LOADER_CLASS_MARKERS):
        return True
    if "loader" in class_type and any(
        token in class_type
        for token in ("model", "checkpoint", "clip", "vae", "unet", "lora")
    ):
        return True
    return any(name in input_names for name in _LOADER_INPUT_NAMES)


def _is_sampler(class_type: str, input_names: tuple[str, ...]) -> bool:
    """Return whether node metadata identifies sampler-style inference work."""

    if "sampler" in class_type:
        return True
    matches = sum(1 for name in _SAMPLER_INPUT_NAMES if name in input_names)
    return matches >= 3 and "latent_image" in input_names


def _is_output(class_type: str) -> bool:
    """Return whether node metadata identifies terminal output work."""

    return "saveimage" in class_type or class_type == "sugarcubes.cubeoutput"
