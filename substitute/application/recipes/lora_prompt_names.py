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

"""Normalize LoRA prompt-token names used by recipe metadata resolution."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

_SUPPORTED_LORA_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})


def prompt_lora_name_for_backend_value(value: str) -> str:
    """Return the prompt-token LoRA name for one Comfy backend model value."""

    return _strip_supported_extension(value)


def normalized_prompt_lora_name(value: str) -> str:
    """Return a stable lookup key for prompt LoRA names in recipe metadata."""

    return _strip_supported_extension(value).replace("\\", "/").casefold()


def backend_value_candidates_for_prompt_lora_name(prompt_name: str) -> tuple[str, ...]:
    """Return likely Comfy backend values for one inline prompt LoRA name."""

    candidates: list[str] = []
    _append_candidate_variants(candidates, prompt_name)
    if _extension_for_value(prompt_name) not in _SUPPORTED_LORA_EXTENSIONS:
        _append_candidate_variants(candidates, f"{prompt_name}.safetensors")
    return tuple(candidates)


def _append_candidate_variants(candidates: list[str], value: str) -> None:
    """Append slash variants for one candidate value without duplicates."""

    for candidate in (value, value.replace("/", "\\"), value.replace("\\", "/")):
        if candidate not in candidates:
            candidates.append(candidate)


def _strip_supported_extension(value: str) -> str:
    """Strip a final LoRA model extension while preserving authored separators."""

    extension = _extension_for_value(value)
    if extension in _SUPPORTED_LORA_EXTENSIONS:
        return value[: -len(extension)]
    return value


def _extension_for_value(value: str) -> str:
    """Return the final path extension for Windows or POSIX-style LoRA values."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


__all__ = [
    "backend_value_candidates_for_prompt_lora_name",
    "normalized_prompt_lora_name",
    "prompt_lora_name_for_backend_value",
]
