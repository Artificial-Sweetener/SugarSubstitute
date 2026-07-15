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

"""Build prompt LoRA diagnostic fields without logging full prompt text."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath, PureWindowsPath

_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})


def lora_prompt_context(
    prompt_name: str,
    *,
    prefix: str = "lora",
) -> dict[str, object]:
    """Return normalized diagnostic fields for one prompt LoRA reference."""

    normalized_prefix = _normalized_prefix(prefix)
    return {
        f"{normalized_prefix}_prompt_name": prompt_name,
        f"{normalized_prefix}_prompt_name_length": len(prompt_name),
        f"{normalized_prefix}_prompt_name_sha256_12": hashlib.sha256(
            prompt_name.encode("utf-8")
        ).hexdigest()[:12],
        f"{normalized_prefix}_prompt_lookup_key": _prompt_lookup_key(prompt_name),
        f"{normalized_prefix}_backend_lookup_key": _backend_lookup_key(
            _with_known_extension(prompt_name)
        ),
        f"{normalized_prefix}_has_path_separator": _has_path_separator(prompt_name),
    }


def lora_source_range_context(
    start: int,
    end: int,
    *,
    prefix: str = "lora",
) -> dict[str, object]:
    """Return source-range diagnostic fields for one prompt LoRA reference."""

    normalized_prefix = _normalized_prefix(prefix)
    return {
        f"{normalized_prefix}_source_start": start,
        f"{normalized_prefix}_source_end": end,
        f"{normalized_prefix}_source_length": max(0, end - start),
    }


def _normalized_prefix(prefix: str) -> str:
    """Return a non-empty key prefix suitable for structured log fields."""

    normalized = prefix.strip().replace("-", "_")
    return normalized or "lora"


def _with_known_extension(value: str) -> str:
    """Append the default LoRA extension when the value lacks a known extension."""

    if _extension_for_value(value) in _SUPPORTED_MODEL_EXTENSIONS:
        return value
    return f"{value}.safetensors"


def _extension_for_value(value: str) -> str:
    """Return the final model extension from one platform-neutral path."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


def _strip_supported_extension(value: str) -> str:
    """Strip a supported model extension while preserving path separators."""

    extension = _extension_for_value(value)
    if extension in _SUPPORTED_MODEL_EXTENSIONS:
        return value[: -len(extension)]
    return value


def _prompt_lookup_key(value: str) -> str:
    """Return the normalized extensionless prompt lookup key."""

    return _strip_supported_extension(value).replace("\\", "/").casefold()


def _backend_lookup_key(value: str) -> str:
    """Return the normalized backend-value lookup key."""

    return value.replace("\\", "/").casefold()


def _has_path_separator(value: str) -> bool:
    """Return whether a prompt LoRA name includes an explicit folder path."""

    return "\\" in value or "/" in value


__all__ = [
    "lora_prompt_context",
    "lora_source_range_context",
]
