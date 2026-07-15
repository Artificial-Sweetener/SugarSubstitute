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

"""Resolve prompt LoRA references into deterministic visual states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast

from substitute.shared.logging.logger import get_logger

from .prompt_lora_catalog_service import (
    PromptLoraCatalogItem,
    PromptLoraCatalogLookup,
    PromptLoraCatalogLookupResult,
)

_LOGGER = get_logger("application.prompt_editor.prompt_lora_resolution_service")


class PromptLoraResolutionStatus(str, Enum):
    """Enumerate authoritative prompt LoRA resolution states."""

    FOUND = "found"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    PENDING_NO_AUTHORITY = "pending_no_authority"
    CATALOG_UNAVAILABLE = "catalog_unavailable"


@dataclass(frozen=True, slots=True)
class PromptLoraResolution:
    """Describe one resolved prompt LoRA reference."""

    status: PromptLoraResolutionStatus
    catalog_item: PromptLoraCatalogItem | None
    authority: bool
    match_source: str
    status_reason: str
    ambiguity_candidate_count: int = 0

    @property
    def is_found(self) -> bool:
        """Return whether the LoRA is authoritatively installed."""

        return self.status is PromptLoraResolutionStatus.FOUND

    @property
    def is_error(self) -> bool:
        """Return whether the LoRA should render with error treatment."""

        return self.status in {
            PromptLoraResolutionStatus.MISSING,
            PromptLoraResolutionStatus.AMBIGUOUS,
        }

    @property
    def has_pending_authority(self) -> bool:
        """Return whether the LoRA is waiting on authoritative catalog data."""

        return self.status in {
            PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
            PromptLoraResolutionStatus.CATALOG_UNAVAILABLE,
        }


class PromptLoraResolutionService:
    """Resolve prompt LoRA names against the active catalog authority."""

    def __init__(self, catalog: PromptLoraCatalogLookup | None) -> None:
        """Store the catalog dependency used for deterministic resolution."""

        self._catalog = catalog

    def resolve(self, prompt_name: str) -> PromptLoraResolution:
        """Return the deterministic resolution for one prompt LoRA name."""

        if self._catalog is None:
            return PromptLoraResolution(
                status=PromptLoraResolutionStatus.CATALOG_UNAVAILABLE,
                catalog_item=None,
                authority=False,
                match_source="catalog_unavailable",
                status_reason="catalog_service_absent",
            )
        lookup = self._lookup(prompt_name)
        has_authority = self._has_authority()
        if not has_authority:
            return PromptLoraResolution(
                status=PromptLoraResolutionStatus.PENDING_NO_AUTHORITY,
                catalog_item=lookup.item,
                authority=False,
                match_source=lookup.match_source,
                status_reason="catalog_not_authoritative",
                ambiguity_candidate_count=lookup.ambiguous_candidate_count,
            )
        if lookup.item is not None:
            return PromptLoraResolution(
                status=PromptLoraResolutionStatus.FOUND,
                catalog_item=lookup.item,
                authority=True,
                match_source=lookup.match_source,
                status_reason="authoritative_match",
            )
        if lookup.ambiguous_candidate_count > 1 or lookup.match_source.startswith(
            "ambiguous_"
        ):
            return PromptLoraResolution(
                status=PromptLoraResolutionStatus.AMBIGUOUS,
                catalog_item=None,
                authority=True,
                match_source=lookup.match_source,
                status_reason="authoritative_ambiguous",
                ambiguity_candidate_count=lookup.ambiguous_candidate_count,
            )
        return PromptLoraResolution(
            status=PromptLoraResolutionStatus.MISSING,
            catalog_item=None,
            authority=True,
            match_source=lookup.match_source,
            status_reason="authoritative_missing",
        )

    def _lookup(self, prompt_name: str) -> PromptLoraCatalogLookupResult:
        """Return a catalog lookup result using the richest available API."""

        if self._catalog is None:
            raise RuntimeError("LoRA catalog is absent.")
        lookup_lora = getattr(self._catalog, "lookup_lora", None)
        if callable(lookup_lora):
            return cast(PromptLoraCatalogLookupResult, lookup_lora(prompt_name))
        return PromptLoraCatalogLookupResult(
            match_source="legacy_find_lora",
            item=self._catalog.find_lora(prompt_name),
        )

    def _has_authority(self) -> bool:
        """Return whether the catalog can make authoritative LoRA decisions."""

        if self._catalog is None:
            return False
        can_report_absence = getattr(self._catalog, "can_report_lora_absence", None)
        if callable(can_report_absence):
            return bool(can_report_absence())
        return True


__all__ = [
    "PromptLoraResolution",
    "PromptLoraResolutionService",
    "PromptLoraResolutionStatus",
]
