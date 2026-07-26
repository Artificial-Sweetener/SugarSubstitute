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

"""Own stable base-drag placement geometry cache state."""

from __future__ import annotations

from .observability import log_reorder_drag_event
from .reorder_geometry_cache_keys import PromptReorderPlacementGeometryCacheKey
from .reorder_geometry_metrics import PromptReorderGeometryMetrics
from .reorder_placement_geometry import PromptReorderPlacementSnapshot


class PromptReorderPlacementGeometryCache:
    """Own the single stable base-drag placement publication."""

    def __init__(self, *, metrics: PromptReorderGeometryMetrics) -> None:
        """Initialize an empty exact-identity cache."""

        self._metrics = metrics
        self._key: PromptReorderPlacementGeometryCacheKey | None = None
        self._snapshot: PromptReorderPlacementSnapshot | None = None

    def clear(self, *, reason: str) -> None:
        """Invalidate the stable placement publication."""

        had_cache = self._snapshot is not None
        self._key = None
        self._snapshot = None
        if had_cache:
            log_reorder_drag_event(
                "cache.base_drag_placement.invalidate",
                reason=reason,
            )

    def get(
        self,
        key: PromptReorderPlacementGeometryCacheKey,
    ) -> PromptReorderPlacementSnapshot | None:
        """Return the stable placement snapshot for an exact identity."""

        if self._key == key and self._snapshot is not None:
            self._metrics.base_placement_hit_count += 1
            return self._snapshot
        self._metrics.base_placement_miss_count += 1
        return None

    def store(
        self,
        *,
        key: PromptReorderPlacementGeometryCacheKey,
        snapshot: PromptReorderPlacementSnapshot,
    ) -> None:
        """Store one stable placement publication."""

        self._key = key
        self._snapshot = snapshot


__all__ = ["PromptReorderPlacementGeometryCache"]
