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

"""Define application DTOs for model-enriched Comfy choice lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitute.application.model_metadata.model_catalog_service import (
    ModelCatalogItem,
    ModelThumbnailVariant,
)


@dataclass(frozen=True, slots=True)
class RichChoiceItem:
    """Describe one exact Comfy choice with optional model metadata enrichment."""

    value: str
    title: str
    subtitle: str | None
    search_text: str
    model_kind: str | None
    catalog_item: ModelCatalogItem | None
    thumbnail_variants: tuple[ModelThumbnailVariant, ...]
    is_enriched: bool
    is_ambiguous: bool
    is_selectable: bool = True


@dataclass(frozen=True, slots=True)
class RichChoiceResolution:
    """Describe whether a Comfy LIST field should use the rich picker."""

    items: tuple[RichChoiceItem, ...]
    should_use_rich_picker: bool
    matched_kinds: tuple[str, ...]
    option_count: int
    enriched_count: int
    ambiguous_count: int
    unmatched_count: int
    reason: str
    unavailable_reason: str | None = None


class RichChoiceSource(Protocol):
    """Provide current and refreshed rich-choice resolutions to widgets."""

    def current_resolution(self) -> RichChoiceResolution:
        """Return the latest available rich-choice resolution."""

    def refresh(self) -> RichChoiceResolution:
        """Refresh model metadata for the relevant kinds and return a resolution."""


__all__ = [
    "RichChoiceItem",
    "RichChoiceResolution",
    "RichChoiceSource",
]
