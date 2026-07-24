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

"""Define immutable values and the read port shared by LoRA catalog consumers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from substitute.domain.model_metadata import STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class PromptLoraThumbnailVariant:
    """Reference one prepared LoRA thumbnail asset safe for presentation use."""

    size: int
    storage_key: str
    width: int
    height: int
    content_format: str
    byte_size: int
    role: str = STANDARD_THUMBNAIL_ROLE


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogItem:
    """Describe one LoRA record ready for prompt picker and renderer use."""

    display_name: str
    display_subtitle: str | None
    prompt_name: str
    backend_value: str
    relative_path: str
    folder: str
    basename: str
    extension: str
    thumbnail_variants: tuple[PromptLoraThumbnailVariant, ...]
    base_model: str | None
    trained_words: tuple[str, ...]
    tags: tuple[str, ...]
    model_page_url: str | None
    collision_key: str
    collision_count: int
    has_collision: bool
    search_text: str


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogSnapshot:
    """Store one immutable LoRA catalog generation plus lookup indexes.

    Bootstrap snapshots are allowed to prove a LoRA exists from persisted local
    metadata, but only authoritative Backend-derived snapshots can prove absence.
    """

    items: tuple[PromptLoraCatalogItem, ...]
    prompt_name_items: Mapping[str, PromptLoraCatalogItem]
    backend_value_items: Mapping[str, PromptLoraCatalogItem]
    backend_prompt_items: Mapping[str, PromptLoraCatalogItem]
    collision_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    autocomplete_exact_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    path_suffix_items: Mapping[str, tuple[PromptLoraCatalogItem, ...]]
    model_generation: int
    revision: int
    authoritative: bool = True


@dataclass(frozen=True, slots=True)
class PromptLoraCatalogLookupResult:
    """Describe how one prompt LoRA lookup resolved against a snapshot."""

    match_source: str
    bare_collision_match_count: int = 0
    ambiguous_candidate_count: int = 0
    fallback_candidate_count: int = 0
    selected_fallback_rank: int | None = None
    item: PromptLoraCatalogItem | None = None

    @property
    def result(self) -> PromptLoraCatalogItem | None:
        """Return the matched LoRA item for compatibility with older tests."""

        return self.item


class PromptLoraCatalogLookup(Protocol):
    """Describe read-only LoRA catalog lookup needed by prompt syntax services."""

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return installed LoRA records without loading the backend catalog."""

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return picker-ready LoRA records for the current Comfy model list."""

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the catalog item matching one prompt LoRA reference."""


__all__ = [
    "PromptLoraCatalogItem",
    "PromptLoraCatalogLookup",
    "PromptLoraCatalogLookupResult",
    "PromptLoraCatalogSnapshot",
    "PromptLoraThumbnailVariant",
]
