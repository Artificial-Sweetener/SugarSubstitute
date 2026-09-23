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

"""Define provider-neutral picker catalog records and lookup contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.model_metadata.model_catalog_provider import (
    ModelProviderLink,
)
from substitute.domain.model_metadata import STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class ModelThumbnailVariant:
    """Reference one prepared model thumbnail asset safe for presentation use."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class ModelCatalogItem:
    """Describe one Comfy-visible model enriched with cached provider metadata."""

    kind: str
    display_name: str
    display_subtitle: str | None
    backend_value: str
    relative_path: str
    folder: str
    basename: str
    extension: str
    thumbnail_variants: tuple[ModelThumbnailVariant, ...]
    base_model: str | None
    trained_words: tuple[str, ...]
    tags: tuple[str, ...]
    model_page_url: str | None
    collision_key: str
    collision_count: int
    has_collision: bool
    search_text: str
    provider_name: str | None = None
    provider_model_id: str | None = None
    provider_model_version_id: str | None = None
    provider_model_name: str | None = None
    provider_model_version_name: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None
    provider_links: tuple[ModelProviderLink, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelCatalogSnapshot:
    """Store one canonical model catalog generation for a single kind."""

    kind: str
    items: tuple[ModelCatalogItem, ...]
    generation: int


class ModelCatalogLookup(Protocol):
    """Describe picker-ready catalog lookup for metadata-backed model selectors."""

    def list_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Return picker-ready model records for one model kind."""

    def refresh_models(self, kind: str) -> tuple[ModelCatalogItem, ...]:
        """Reload and return picker-ready model records for one model kind."""

    def invalidate(self, kind: str | None = None) -> None:
        """Clear cached snapshots for one kind or all kinds."""


__all__ = [
    "ModelCatalogItem",
    "ModelCatalogLookup",
    "ModelCatalogSnapshot",
    "ModelThumbnailVariant",
]
