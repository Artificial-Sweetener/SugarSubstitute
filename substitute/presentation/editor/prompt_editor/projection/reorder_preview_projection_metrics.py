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

"""Own typed counters for reorder preview projection work."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PromptReorderPreviewProjectionMetrics:
    """Record structural work without participating in projection policy."""

    projection_snapshot_rebuild_count: int = 0
    full_layout_count: int = 0
    incremental_layout_count: int = 0
    exact_layout_reuse_count: int = 0
    active_cache_hit_count: int = 0
    lru_cache_hit_count: int = 0
    cache_miss_count: int = 0

    def reset(self) -> None:
        """Reset counters at the start of one measured gesture."""

        self.projection_snapshot_rebuild_count = 0
        self.full_layout_count = 0
        self.incremental_layout_count = 0
        self.exact_layout_reuse_count = 0
        self.active_cache_hit_count = 0
        self.lru_cache_hit_count = 0
        self.cache_miss_count = 0

    def snapshot(self) -> dict[str, object]:
        """Return the stable diagnostic counter schema."""

        return {
            "projection_snapshot_rebuild_count": (
                self.projection_snapshot_rebuild_count
            ),
            "preview_projection_full_layout_count": self.full_layout_count,
            "preview_projection_incremental_layout_count": (
                self.incremental_layout_count
            ),
            "preview_projection_exact_layout_reuse_count": (
                self.exact_layout_reuse_count
            ),
            "preview_projection_active_cache_hit_count": (self.active_cache_hit_count),
            "preview_projection_lru_cache_hit_count": self.lru_cache_hit_count,
            "preview_projection_cache_miss_count": self.cache_miss_count,
        }


__all__ = ["PromptReorderPreviewProjectionMetrics"]
