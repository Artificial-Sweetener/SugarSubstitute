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

"""Define generic media wall item DTOs for Qt presentation adapters."""

from __future__ import annotations

from dataclasses import dataclass

_STANDARD_THUMBNAIL_ROLE = "standard"


@dataclass(frozen=True, slots=True)
class ThumbnailVariantReference:
    """Reference one prepared thumbnail asset by logical storage key."""

    storage_key: str
    size: int
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = _STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class MediaWallItem:
    """Describe one item rendered by the reusable media wall view."""

    item_id: str
    title: str
    subtitle: str | None
    aspect_ratio: float
    thumbnail_variants: tuple[ThumbnailVariantReference, ...]
    payload: object
    tooltip: str | None = None


__all__ = ["MediaWallItem", "ThumbnailVariantReference"]
