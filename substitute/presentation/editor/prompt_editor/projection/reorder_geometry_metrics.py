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

"""Own typed structural counters for prompt reorder geometry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PromptReorderGeometryMetrics:
    """Record cache, reuse, scroll, and duration evidence without geometry policy."""

    base_chip_hit_count: int = 0
    base_chip_miss_count: int = 0
    base_chip_preview_reuse_count: int = 0
    base_placement_hit_count: int = 0
    base_placement_miss_count: int = 0
    preview_chip_hit_count: int = 0
    preview_chip_miss_count: int = 0
    preview_chip_live_reuse_count: int = 0
    preview_reused_chip_count: int = 0
    preview_rebuilt_chip_count: int = 0
    preview_reuse_rejected_count: int = 0
    scroll_translated_chip_count: int = 0
    scroll_rebuilt_chip_count: int = 0
    live_chip_hit_count: int = 0
    live_chip_miss_count: int = 0
    max_base_chip_ms: float = 0.0
    max_base_placement_ms: float = 0.0
    max_preview_chip_ms: float = 0.0

    def reset(self) -> None:
        """Reset all counters at one gesture boundary."""

        self.base_chip_hit_count = 0
        self.base_chip_miss_count = 0
        self.base_chip_preview_reuse_count = 0
        self.base_placement_hit_count = 0
        self.base_placement_miss_count = 0
        self.preview_chip_hit_count = 0
        self.preview_chip_miss_count = 0
        self.preview_chip_live_reuse_count = 0
        self.preview_reused_chip_count = 0
        self.preview_rebuilt_chip_count = 0
        self.preview_reuse_rejected_count = 0
        self.scroll_translated_chip_count = 0
        self.scroll_rebuilt_chip_count = 0
        self.live_chip_hit_count = 0
        self.live_chip_miss_count = 0
        self.max_base_chip_ms = 0.0
        self.max_base_placement_ms = 0.0
        self.max_preview_chip_ms = 0.0

    def snapshot(self) -> dict[str, object]:
        """Return the stable diagnostics schema consumed by harnesses."""

        return {
            "base_chip_geometry_cache_hit_count": self.base_chip_hit_count,
            "base_chip_geometry_cache_miss_count": self.base_chip_miss_count,
            "base_chip_geometry_preview_reuse_count": (
                self.base_chip_preview_reuse_count
            ),
            "base_placement_cache_hit_count": self.base_placement_hit_count,
            "base_placement_cache_miss_count": self.base_placement_miss_count,
            "preview_chip_geometry_cache_hit_count": self.preview_chip_hit_count,
            "preview_chip_geometry_cache_miss_count": self.preview_chip_miss_count,
            "preview_chip_geometry_live_reuse_count": (
                self.preview_chip_live_reuse_count
            ),
            "preview_chip_geometry_reused_chip_count": (self.preview_reused_chip_count),
            "preview_chip_geometry_rebuilt_chip_count": (
                self.preview_rebuilt_chip_count
            ),
            "preview_chip_geometry_reuse_rejected_count": (
                self.preview_reuse_rejected_count
            ),
            "scroll_translated_chip_geometry_count": (
                self.scroll_translated_chip_count
            ),
            "scroll_rebuilt_chip_geometry_count": self.scroll_rebuilt_chip_count,
            "live_chip_geometry_cache_hit_count": self.live_chip_hit_count,
            "live_chip_geometry_cache_miss_count": self.live_chip_miss_count,
            "max_base_chip_geometry_ms": f"{self.max_base_chip_ms:.3f}",
            "max_base_placement_ms": f"{self.max_base_placement_ms:.3f}",
            "max_preview_chip_geometry_ms": f"{self.max_preview_chip_ms:.3f}",
        }

    def record_scroll_reuse(
        self,
        *,
        translated_chip_count: int,
        rebuilt_chip_count: int,
    ) -> None:
        """Record bounded work performed for one scroll translation."""

        self.scroll_translated_chip_count += translated_chip_count
        self.scroll_rebuilt_chip_count += rebuilt_chip_count


__all__ = ["PromptReorderGeometryMetrics"]
