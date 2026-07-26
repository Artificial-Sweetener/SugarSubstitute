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

"""Own bounded cache identity and reuse for reorder preview frames."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass

from PySide6.QtGui import QFont, QPalette

from substitute.application.appearance import SemanticPalette
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)

from .observability import log_reorder_drag_event
from .prepared_frame import PromptProjectionPreparedFrame
from .reorder_preview import PromptReorderProjectionSnapshot
from .reorder_preview_layout_builder import PromptReorderPreviewLayoutIdentity
from .reorder_preview_projection_contracts import (
    PromptReorderPreviewProjectionContext,
    PromptReorderProjectionSnapshotCacheKey,
)
from .reorder_preview_projection_metrics import (
    PromptReorderPreviewProjectionMetrics,
)

_DEFAULT_CACHE_LIMIT = 16


@dataclass(frozen=True, slots=True)
class PromptReorderProjectionFrameCacheEntry:
    """Store one reusable reorder projection document and prepared frame."""

    document: PromptProjectionDocument
    frame: PromptProjectionPreparedFrame
    text_length: int
    rendered_range_count: int


class PromptReorderPreviewFrameCache:
    """Own bounded target-revisit cache state and its complete key policy."""

    def __init__(
        self,
        *,
        metrics: PromptReorderPreviewProjectionMetrics,
        limit: int = _DEFAULT_CACHE_LIMIT,
    ) -> None:
        """Initialize one bounded least-recently-used cache."""

        self._metrics = metrics
        self._limit = limit
        self._entries: OrderedDict[
            PromptReorderProjectionSnapshotCacheKey,
            PromptReorderProjectionFrameCacheEntry,
        ] = OrderedDict()

    def key_for(
        self,
        snapshot: PromptReorderProjectionSnapshot,
        *,
        context: PromptReorderPreviewProjectionContext,
        layout_key: Hashable | None,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderProjectionSnapshotCacheKey:
        """Return complete geometry and content identity for one frame."""

        snapshot_hash = _snapshot_hash(snapshot)
        return PromptReorderProjectionSnapshotCacheKey(
            source_revision=context.source_revision,
            viewport_width=context.viewport_width,
            layout_width_x100=int(round(context.layout_width * 100.0)),
            layout_key=layout_key,
            active_drop_target_identity=context.active_drop_target_identity,
            render_plan_hash=_render_plan_hash(snapshot),
            font_key=font.toString(),
            palette_cache_key=int(palette.cacheKey()),
            semantic_palette_hash=_safe_key_hash(semantic_palette),
            snapshot_hash=snapshot_hash,
            text_length=len(snapshot.document_view.source_text),
            rendered_ranges=tuple(
                sorted(snapshot.chip_rendered_ranges_by_index.items())
            ),
            owned_ranges=tuple(sorted(snapshot.chip_owned_ranges_by_index.items())),
            gap_ranges=tuple(sorted(snapshot.gap_ranges_by_index.items())),
        )

    def get(
        self,
        key: PromptReorderProjectionSnapshotCacheKey,
    ) -> PromptReorderProjectionFrameCacheEntry | None:
        """Return and refresh one cached frame, recording hit or miss."""

        entry = self._entries.get(key)
        if entry is None:
            self._metrics.cache_miss_count += 1
            log_reorder_drag_event(
                "cache.preview_projection.miss",
                cache_size=len(self._entries),
                **self.diagnostic_context(key),
            )
            return None
        self._entries.move_to_end(key)
        self._metrics.lru_cache_hit_count += 1
        log_reorder_drag_event(
            "cache.preview_projection.hit",
            cache_size=len(self._entries),
            text_length=entry.text_length,
            rendered_range_count=entry.rendered_range_count,
            **self.diagnostic_context(key),
        )
        return entry

    def store(
        self,
        *,
        key: PromptReorderProjectionSnapshotCacheKey,
        snapshot: PromptReorderProjectionSnapshot,
        document: PromptProjectionDocument,
        frame: PromptProjectionPreparedFrame,
    ) -> None:
        """Store a frame and evict least-recent entries beyond the bound."""

        self._entries[key] = PromptReorderProjectionFrameCacheEntry(
            document=document,
            frame=frame,
            text_length=len(snapshot.document_view.source_text),
            rendered_range_count=len(snapshot.chip_rendered_ranges_by_index),
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self._limit:
            _old_key, old_entry = self._entries.popitem(last=False)
            log_reorder_drag_event(
                "cache.preview_projection.evict",
                cache_size=len(self._entries),
                text_length=old_entry.text_length,
                rendered_range_count=old_entry.rendered_range_count,
            )

    def clear(self, *, reason: str) -> None:
        """Invalidate all cached frames when a cache identity input changes."""

        cache_size = len(self._entries)
        self._entries.clear()
        if cache_size:
            log_reorder_drag_event(
                "cache.preview_projection.invalidate",
                reason=reason,
                cache_size=cache_size,
            )

    @staticmethod
    def layout_identity(
        key: PromptReorderProjectionSnapshotCacheKey,
    ) -> PromptReorderPreviewLayoutIdentity:
        """Return layout-affecting identity without target or prompt content."""

        return PromptReorderPreviewLayoutIdentity(
            source_revision=key.source_revision,
            viewport_width=key.viewport_width,
            layout_width_x100=key.layout_width_x100,
            font_key=key.font_key,
            palette_cache_key=key.palette_cache_key,
            semantic_palette_hash=key.semantic_palette_hash,
        )

    @staticmethod
    def layout_identity_for_inputs(
        *,
        context: PromptReorderPreviewProjectionContext,
        font: QFont,
        palette: QPalette,
        semantic_palette: SemanticPalette | None,
    ) -> PromptReorderPreviewLayoutIdentity:
        """Return layout-affecting identity for a pending frame build."""

        return PromptReorderPreviewLayoutIdentity(
            source_revision=context.source_revision,
            viewport_width=context.viewport_width,
            layout_width_x100=int(round(context.layout_width * 100.0)),
            font_key=font.toString(),
            palette_cache_key=int(palette.cacheKey()),
            semantic_palette_hash=_safe_key_hash(semantic_palette),
        )

    @staticmethod
    def diagnostic_context(
        key: PromptReorderProjectionSnapshotCacheKey,
    ) -> dict[str, object]:
        """Return prompt-safe diagnostics for one frame-cache identity."""

        return {
            "projection_cache_text_length": key.text_length,
            "projection_cache_snapshot_hash": key.snapshot_hash,
            "projection_cache_rendered_range_count": len(key.rendered_ranges),
            "projection_cache_owned_range_count": len(key.owned_ranges),
            "projection_cache_gap_range_count": len(key.gap_ranges),
            "source_revision": key.source_revision,
            "projection_cache_viewport_width": key.viewport_width,
            "projection_cache_layout_width_x100": key.layout_width_x100,
            "projection_cache_layout_hash": _safe_key_hash(key.layout_key),
            "projection_cache_target_hash": _safe_key_hash(
                key.active_drop_target_identity
            ),
            "projection_cache_render_plan_hash": key.render_plan_hash,
            "projection_cache_font_hash": _safe_key_hash(key.font_key),
            "projection_cache_palette_key": key.palette_cache_key,
            "projection_cache_semantic_palette_hash": key.semantic_palette_hash,
        }


def _snapshot_hash(snapshot: PromptReorderProjectionSnapshot) -> str:
    """Return a prompt-safe identity for one projection snapshot."""

    digest = hashlib.sha256()
    digest.update(snapshot.document_view.source_text.encode("utf-8"))
    digest.update(repr(sorted(snapshot.chip_rendered_ranges_by_index.items())).encode())
    digest.update(repr(sorted(snapshot.chip_owned_ranges_by_index.items())).encode())
    digest.update(repr(sorted(snapshot.gap_ranges_by_index.items())).encode())
    return digest.hexdigest()[:16]


def _render_plan_hash(snapshot: PromptReorderProjectionSnapshot) -> str:
    """Return a prompt-safe identity for renderer-visible syntax inputs."""

    return hashlib.sha256(repr(snapshot.render_plan).encode("utf-8")).hexdigest()[:16]


def _safe_key_hash(key: object) -> str:
    """Return a compact diagnostic hash without logging prompt text."""

    if key is None:
        return "none"
    return hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]


__all__ = [
    "PromptReorderProjectionFrameCacheEntry",
    "PromptReorderPreviewFrameCache",
]
