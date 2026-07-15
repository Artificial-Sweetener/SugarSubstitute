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

"""Tests for CivitAI cache maintenance orchestration."""

from __future__ import annotations

from substitute.application.civitai import CivitaiCacheService
from substitute.application.ports.civitai_cache_repository import CivitaiCacheSummary


class _CacheRepository:
    """Record cache repository calls for service tests."""

    def __init__(self) -> None:
        """Initialize call tracking."""

        self.calls: list[str] = []

    def cache_summary(self) -> CivitaiCacheSummary:
        """Return an empty cache summary."""

        self.calls.append("summary")
        return CivitaiCacheSummary(
            provider_record_count=0,
            thumbnail_source_count=0,
            thumbnail_variant_count=0,
            thumbnail_bytes=0,
        )

    def clear_civitai_thumbnails(self) -> None:
        """Record thumbnail clear."""

        self.calls.append("clear-thumbnails")

    def clear_civitai_metadata(self) -> None:
        """Record metadata clear."""

        self.calls.append("clear-metadata")


def test_refresh_civitai_metadata_schedules_background_refresh() -> None:
    """Settings refresh should queue refresh work and invalidate snapshots."""

    repository = _CacheRepository()
    calls: list[str] = []
    service = CivitaiCacheService(
        repository,
        invalidate_model_catalog=lambda: calls.append("invalidate"),
        schedule_metadata_refresh=lambda: calls.append("refresh"),
    )

    service.refresh_civitai_metadata()

    assert calls == ["invalidate", "refresh"]
