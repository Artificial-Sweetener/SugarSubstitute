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

"""Define CivitAI metadata cache maintenance contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class CivitaiCacheSummary:
    """Summarize locally cached CivitAI metadata and thumbnails."""

    provider_record_count: int
    thumbnail_source_count: int
    thumbnail_variant_count: int
    thumbnail_bytes: int


@runtime_checkable
class CivitaiCacheRepository(Protocol):
    """Maintain CivitAI provider metadata and thumbnail caches."""

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return a summary of cached CivitAI data."""

    def clear_civitai_thumbnails(self) -> None:
        """Delete CivitAI thumbnail sources and prepared variants."""

    def clear_civitai_metadata(self) -> None:
        """Delete CivitAI provider records and thumbnails."""


__all__ = ["CivitaiCacheRepository", "CivitaiCacheSummary"]
