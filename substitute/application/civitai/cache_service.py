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

"""Coordinate CivitAI cache maintenance and invalidation."""

from __future__ import annotations

from collections.abc import Callable

from substitute.application.ports.civitai_cache_repository import (
    CivitaiCacheRepository,
    CivitaiCacheSummary,
)


class CivitaiCacheService:
    """Own user-facing CivitAI cache maintenance operations."""

    def __init__(
        self,
        repository: CivitaiCacheRepository,
        *,
        invalidate_model_catalog: Callable[[], None] | None = None,
        schedule_metadata_refresh: Callable[[], None] | None = None,
    ) -> None:
        """Store cache collaborators."""

        self._repository = repository
        self._invalidate_model_catalog = invalidate_model_catalog
        self._schedule_metadata_refresh = schedule_metadata_refresh

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return a summary of locally cached CivitAI data."""

        return self._repository.cache_summary()

    def clear_civitai_thumbnails(self) -> None:
        """Delete cached CivitAI thumbnails and invalidate live model catalogs."""

        self._repository.clear_civitai_thumbnails()
        self._invalidate()

    def clear_civitai_metadata(self) -> None:
        """Delete cached CivitAI metadata and thumbnails."""

        self._repository.clear_civitai_metadata()
        self._invalidate()

    def refresh_civitai_metadata(self) -> None:
        """Queue background CivitAI metadata refresh using current policy."""

        self._invalidate()
        if self._schedule_metadata_refresh is not None:
            self._schedule_metadata_refresh()

    def _invalidate(self) -> None:
        """Invalidate picker snapshots when a collaborator is configured."""

        if self._invalidate_model_catalog is not None:
            self._invalidate_model_catalog()


__all__ = ["CivitaiCacheService"]
