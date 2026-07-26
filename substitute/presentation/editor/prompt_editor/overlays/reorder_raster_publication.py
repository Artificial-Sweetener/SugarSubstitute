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

"""Publish revision-safe reorder raster mappings outside overlay coordination."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from PySide6.QtCore import QObject

from .chip_painter import PromptChipPaintStyle
from .reorder_raster_cache import (
    PromptReorderRasterCache,
    ReorderRasterCacheCounters,
    ReorderRasterEntry,
    ReorderRasterStyleKey,
    reorder_raster_style_key,
)
from .reorder_raster_warm_scheduler import PromptReorderRasterWarmScheduler
from .reorder_visual_cache import PromptReorderChipVisualSnapshot

PromptReorderRasterLane = Literal["live", "preview"]


@dataclass(frozen=True, slots=True, eq=False)
class PromptReorderRasterInputIdentity:
    """Retain one snapshot identity and its raster-relevant style."""

    segment_index: int
    snapshot: PromptReorderChipVisualSnapshot
    style_key: ReorderRasterStyleKey

    def matches(self, other: PromptReorderRasterInputIdentity) -> bool:
        """Compare immutable input identity without hashing snapshot contents."""

        return (
            self.segment_index == other.segment_index
            and self.snapshot is other.snapshot
            and self.style_key == other.style_key
        )


@dataclass(frozen=True, slots=True, eq=False)
class PromptReorderRasterPublicationKey:
    """Identify one complete render-state raster mapping."""

    device_pixel_ratio: float
    inputs: tuple[PromptReorderRasterInputIdentity, ...]

    def matches(self, other: PromptReorderRasterPublicationKey) -> bool:
        """Compare the bounded input sequence using strong snapshot identities."""

        return (
            self.device_pixel_ratio == other.device_pixel_ratio
            and len(self.inputs) == len(other.inputs)
            and all(
                current.matches(candidate)
                for current, candidate in zip(self.inputs, other.inputs, strict=True)
            )
        )


@dataclass(frozen=True, slots=True)
class PromptReorderRasterPublication:
    """Publish one lane's exact input identity and prepared raster entries."""

    key: PromptReorderRasterPublicationKey
    entries_by_index: Mapping[int, ReorderRasterEntry]


@dataclass(frozen=True, slots=True)
class PromptReorderRasterPublicationCounters:
    """Summarize raster publication reuse plus lower pixmap cache work."""

    render_cache_hit_count: int
    render_cache_miss_count: int
    raster_cache: ReorderRasterCacheCounters

    def as_dict(self) -> dict[str, int | float]:
        """Return the stable harness counter schema."""

        return {
            **self.raster_cache.as_dict(),
            "raster_entries_render_cache_hit_count": self.render_cache_hit_count,
            "raster_entries_render_cache_miss_count": self.render_cache_miss_count,
        }


class PromptReorderRasterPublicationOwner:
    """Own live/preview raster reuse, warming, invalidation, and diagnostics."""

    def __init__(
        self,
        *,
        parent: QObject,
        entries_changed: Callable[[], None],
    ) -> None:
        """Create one bounded raster lifecycle for a reorder overlay."""

        self._entries_changed = entries_changed
        self._cache = PromptReorderRasterCache()
        self._warm_scheduler = PromptReorderRasterWarmScheduler(
            parent=parent,
            cache=self._cache,
            entries_changed=self._handle_warmed_entries,
        )
        self._live_publication: PromptReorderRasterPublication | None = None
        self._preview_publication: PromptReorderRasterPublication | None = None
        self._render_cache_hit_count = 0
        self._render_cache_miss_count = 0

    def entries_for(
        self,
        lane: PromptReorderRasterLane,
        *,
        snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot],
        styles_by_index: Mapping[int, PromptChipPaintStyle],
        device_pixel_ratio: float,
    ) -> Mapping[int, ReorderRasterEntry]:
        """Return one lane's raster entries, scheduling bounded missing work."""

        key = _publication_key(
            snapshots_by_index=snapshots_by_index,
            styles_by_index=styles_by_index,
            device_pixel_ratio=device_pixel_ratio,
        )
        publication = self._publication(lane)
        if publication is not None and publication.key.matches(key):
            self._render_cache_hit_count += 1
            return publication.entries_by_index

        entries = self._cache.entries_for_snapshots(
            snapshots_by_index=snapshots_by_index,
            styles_by_index=styles_by_index,
            device_pixel_ratio=device_pixel_ratio,
            build_limit=0,
        )
        if len(entries) < len(key.inputs):
            self._warm_scheduler.request(
                lane,
                snapshots_by_index=snapshots_by_index,
                styles_by_index=styles_by_index,
                device_pixel_ratio=device_pixel_ratio,
            )
        else:
            self._warm_scheduler.cancel(lane)
        publication = PromptReorderRasterPublication(
            key=key,
            entries_by_index=MappingProxyType(entries),
        )
        self._set_publication(lane, publication)
        self._render_cache_miss_count += 1
        return publication.entries_by_index

    def clear(self) -> None:
        """Clear pending work, pixmaps, and both lane publications."""

        self._warm_scheduler.clear()
        self._cache.clear()
        self.invalidate_entries()

    def invalidate_entries(self) -> None:
        """Discard render-state mappings while retaining reusable pixmaps."""

        self._live_publication = None
        self._preview_publication = None

    def counters(self) -> PromptReorderRasterPublicationCounters:
        """Return immutable owner and lower-cache diagnostics."""

        return PromptReorderRasterPublicationCounters(
            render_cache_hit_count=self._render_cache_hit_count,
            render_cache_miss_count=self._render_cache_miss_count,
            raster_cache=self._cache.counters(),
        )

    def _publication(
        self,
        lane: PromptReorderRasterLane,
    ) -> PromptReorderRasterPublication | None:
        """Return the current publication for one named paint lane."""

        if lane == "preview":
            return self._preview_publication
        return self._live_publication

    def _set_publication(
        self,
        lane: PromptReorderRasterLane,
        publication: PromptReorderRasterPublication,
    ) -> None:
        """Replace exactly one named paint-lane publication."""

        if lane == "preview":
            self._preview_publication = publication
        else:
            self._live_publication = publication

    def _handle_warmed_entries(self) -> None:
        """Invalidate mappings and publish one completed warm batch."""

        self.invalidate_entries()
        self._entries_changed()


def _publication_key(
    *,
    snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot],
    styles_by_index: Mapping[int, PromptChipPaintStyle],
    device_pixel_ratio: float,
) -> PromptReorderRasterPublicationKey:
    """Build a deterministic key without deep snapshot equality or integer IDs."""

    return PromptReorderRasterPublicationKey(
        device_pixel_ratio=device_pixel_ratio,
        inputs=tuple(
            PromptReorderRasterInputIdentity(
                segment_index=segment_index,
                snapshot=snapshot,
                style_key=reorder_raster_style_key(styles_by_index[segment_index]),
            )
            for segment_index, snapshot in sorted(snapshots_by_index.items())
            if segment_index in styles_by_index
        ),
    )


__all__ = [
    "PromptReorderRasterInputIdentity",
    "PromptReorderRasterLane",
    "PromptReorderRasterPublication",
    "PromptReorderRasterPublicationCounters",
    "PromptReorderRasterPublicationKey",
    "PromptReorderRasterPublicationOwner",
]
