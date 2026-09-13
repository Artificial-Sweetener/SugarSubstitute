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

"""Derive stable values used by the model picker presentation."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from substitute.application.model_metadata import (
    ModelThumbnailVariant,
    RichChoiceResolution,
)
from substitute.presentation.widgets.media_wall import ThumbnailVariantReference

_SUPPORTED_MODEL_EXTENSIONS = frozenset({".safetensors", ".ckpt", ".pt"})


def fallback_display_label(value: str) -> str:
    """Return a conservative local display label for an unknown backend value."""

    stripped_value = value.strip()
    if not stripped_value:
        return ""
    normalized_value = stripped_value.replace("\\", "/")
    name = PurePosixPath(normalized_value).name
    return strip_supported_extension(name) or stripped_value


def unavailable_resolution(
    previous_resolution: RichChoiceResolution | None,
    error: Exception,
) -> RichChoiceResolution:
    """Return an empty selector resolution after a fresh Backend refresh failure."""

    matched_kinds = (
        () if previous_resolution is None else previous_resolution.matched_kinds
    )
    reason = (
        "model selection unavailable: backend model catalog refresh failed "
        f"({type(error).__name__})"
    )
    return RichChoiceResolution(
        items=(),
        should_use_rich_picker=True,
        matched_kinds=matched_kinds,
        option_count=0
        if previous_resolution is None
        else previous_resolution.option_count,
        enriched_count=0,
        ambiguous_count=0,
        unmatched_count=0,
        reason=reason,
        unavailable_reason=reason,
    )


def clamp_progress_percent(value: float | None) -> float | None:
    """Clamp optional progress to the visible progress range."""

    if value is None:
        return None
    return min(100.0, max(0.0, float(value)))


def strip_supported_extension(value: str) -> str:
    """Strip the final model extension from one path while preserving separators."""

    extension = extension_for_value(value)
    if extension in _SUPPORTED_MODEL_EXTENSIONS:
        return value[: -len(extension)]
    return value


def extension_for_value(value: str) -> str:
    """Return the final file extension from one backend value."""

    windows_suffix = PureWindowsPath(value).suffix
    posix_suffix = PurePosixPath(value).suffix
    return (windows_suffix or posix_suffix).lower()


def thumbnail_refs_from_all_model_variants(
    variants: tuple[ModelThumbnailVariant, ...],
) -> tuple[ThumbnailVariantReference, ...]:
    """Return thumbnail references for all roles, including banner variants."""

    return tuple(
        ThumbnailVariantReference(
            storage_key=variant.storage_key,
            size=variant.size,
            width=variant.width,
            height=variant.height,
            content_format=variant.content_format,
            byte_size=variant.byte_size,
            role=variant.role,
        )
        for variant in variants
    )


__all__ = [
    "clamp_progress_percent",
    "extension_for_value",
    "fallback_display_label",
    "strip_supported_extension",
    "thumbnail_refs_from_all_model_variants",
    "unavailable_resolution",
]
