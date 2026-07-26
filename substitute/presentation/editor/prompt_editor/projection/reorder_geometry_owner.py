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

"""Own cached chip and placement geometry for prompt reorder interaction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import QRectF

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderLayoutView,
)

from .prepared_frame import PromptProjectionPreparedFrame
from .observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from .reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
    chip_geometry_snapshot_context,
)
from .reorder_chip_geometry_cache import PromptReorderChipGeometryCache
from .reorder_geometry import (
    PromptProjectionReorderGeometry,
    reorder_geometry_state,
)
from .reorder_geometry_cache_keys import (
    PromptReorderChipGeometryCacheKey,
    PromptReorderPlacementGeometryCacheKey,
    ReorderGeometrySnapshot,
    reorder_chip_geometry_cache_key,
    reorder_geometry_viewport_rect,
    reorder_live_chip_geometry_cache_key,
    reorder_placement_geometry_cache_key,
)
from .reorder_geometry_diagnostics import (
    reorder_geometry_cache_context,
    reorder_geometry_event_id,
    reorder_geometry_gesture_id,
    reorder_geometry_reason,
    reorder_placement_context,
)
from .reorder_geometry_metrics import PromptReorderGeometryMetrics
from .reorder_placement_geometry import (
    PromptReorderPlacementSnapshot,
    duplicate_reorder_placement_targets,
)
from .reorder_placement_geometry_cache import PromptReorderPlacementGeometryCache
from .reorder_preview_projection_owner import PromptReorderPreviewProjectionOwner
from .reorder_scroll_geometry import build_reorder_geometry_after_scroll

_SLOW_GEOMETRY_MS = 8.0
_SnapshotKind = Literal["preview", "base_drag"]


@dataclass(frozen=True, slots=True)
class PromptReorderGeometryEnvironment:
    """Publish all live geometry inputs from one coherent surface state."""

    live_source_text: str
    live_frame: PromptProjectionPreparedFrame
    viewport_rect: QRectF
    scroll_offset: float
    layout_width: float


class PromptReorderGeometryOwner:
    """Build immutable reorder geometry over one atomic environment snapshot."""

    def __init__(
        self,
        *,
        environment: Callable[[str], PromptReorderGeometryEnvironment],
        preview_projection: PromptReorderPreviewProjectionOwner,
    ) -> None:
        """Store the environment publication and projection frame authority."""

        self._environment = environment
        self._preview_projection = preview_projection
        self._geometry = PromptProjectionReorderGeometry()
        self._metrics = PromptReorderGeometryMetrics()
        self._chip_cache = PromptReorderChipGeometryCache(metrics=self._metrics)
        self._placement_cache = PromptReorderPlacementGeometryCache(
            metrics=self._metrics
        )

    @property
    def projection_geometry(self) -> PromptProjectionReorderGeometry:
        """Return the shared stateless projection-geometry algorithms."""

        return self._geometry

    def reset_counters(self) -> None:
        """Reset per-gesture geometry cache counters."""

        self._metrics.reset()

    def counters(self) -> dict[str, object]:
        """Return the stable prompt-safe geometry counter schema."""

        return self._metrics.snapshot()

    def clear_all(self, *, reason: str) -> None:
        """Invalidate all chip and placement geometry caches."""

        self._chip_cache.clear_live(reason=reason)
        self._chip_cache.clear_preview(reason=reason)
        self._chip_cache.clear_base_drag(reason=reason)
        self._placement_cache.clear(reason=reason)

    def clear_live(self, *, reason: str) -> None:
        """Invalidate live chip geometry cache entries."""

        self._chip_cache.clear_live(reason=reason)

    def clear_preview(self, *, reason: str) -> None:
        """Invalidate preview chip geometry cache entries."""

        self._chip_cache.clear_preview(reason=reason)

    def clear_base_drag(self, *, reason: str) -> None:
        """Invalidate stable drag chip and placement geometry entries."""

        self._chip_cache.clear_base_drag(reason=reason)
        self._placement_cache.clear(reason=reason)

    def live_chip_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_rendered_ranges_by_index: dict[int, tuple[int, int]],
        chip_owned_ranges_by_index: dict[int, tuple[tuple[int, int], ...]],
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached live chip geometry from one environment publication."""

        started_at = reorder_drag_started_at()
        environment = self._environment("reorder_live_chip_geometry")
        cache_key = reorder_live_chip_geometry_cache_key(
            source_text=environment.live_source_text,
            chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
            chip_owned_ranges_by_index=chip_owned_ranges_by_index,
            layout_view=layout_view,
            projection_layout_identity=id(environment.live_frame),
            viewport_rect=environment.viewport_rect,
            scroll_offset=environment.scroll_offset,
            layout_width=environment.layout_width,
        )
        snapshot = self._chip_cache.live(cache_key)
        cache_hit = snapshot is not None
        if snapshot is None:
            scroll_candidate = self._chip_cache.live_scroll_candidate(cache_key)
            if scroll_candidate is None:
                snapshot = self._geometry.reorder_chip_geometry_snapshot(
                    state=reorder_geometry_state(environment.live_frame.geometry),
                    layout_view=layout_view,
                    chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
                    chip_owned_ranges_by_index=chip_owned_ranges_by_index,
                    viewport_rect=environment.viewport_rect,
                    scroll_offset=environment.scroll_offset,
                )
            else:
                previous_key, previous_snapshot = scroll_candidate
                scroll_result = build_reorder_geometry_after_scroll(
                    self._geometry,
                    reorder_geometry_state(environment.live_frame.geometry),
                    layout_view=layout_view,
                    chip_rendered_ranges_by_index=chip_rendered_ranges_by_index,
                    chip_owned_ranges_by_index=chip_owned_ranges_by_index,
                    previous_snapshot=previous_snapshot,
                    previous_viewport_rect=reorder_geometry_viewport_rect(
                        previous_key.viewport
                    ),
                    current_viewport_rect=environment.viewport_rect,
                    current_scroll_offset=environment.scroll_offset,
                )
                snapshot = scroll_result.snapshot
                self._metrics.record_scroll_reuse(
                    translated_chip_count=scroll_result.translated_chip_count,
                    rebuilt_chip_count=scroll_result.rebuilt_chip_count,
                )
            self._chip_cache.store_live(
                key=cache_key,
                snapshot=snapshot,
            )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_live_chip_geometry_snapshot",
            started_at=started_at,
            cache_hit=cache_hit,
            **chip_geometry_snapshot_context(snapshot),
        )
        self._log_slow_chip_snapshot(
            elapsed_ms,
            snapshot=snapshot,
            snapshot_kind="live",
        )
        return snapshot

    def preview_chip_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached chip geometry for the active preview frame."""

        return self._projected_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
            frame=self._preview_projection.preview_frame,
            snapshot_kind="preview",
        )

    def base_drag_chip_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return cached chip geometry for the stable base-drag frame."""

        return self._projected_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
            frame=self._preview_projection.base_drag_frame,
            snapshot_kind="base_drag",
        )

    def base_drag_placement_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
    ) -> PromptReorderPlacementSnapshot:
        """Return cached placement geometry for the stable drag frame."""

        base_drag_frame = self._preview_projection.base_drag_frame
        environment = self._environment(
            "reorder_base_drag_placement" if base_drag_frame is not None else ""
        )
        if base_drag_frame is None:
            return self._empty_placement_snapshot(environment)
        started_at = reorder_drag_started_at()
        cache_key = self._placement_key(
            snapshot=snapshot,
            layout_view=layout_view,
            frame=base_drag_frame,
            environment=environment,
        )
        preview_state = self._preview_projection.preview_state
        cached = self._placement_cache.get(cache_key)
        if cached is not None:
            log_reorder_drag_event(
                "cache.base_drag_placement.hit",
                gesture_id=reorder_geometry_gesture_id(preview_state),
                event_id=reorder_geometry_event_id(preview_state),
                **reorder_geometry_cache_context(cache_key),
            )
            log_reorder_drag_timing(
                "surface.reorder_base_drag_placement_snapshot",
                started_at=started_at,
                gesture_id=reorder_geometry_gesture_id(preview_state),
                event_id=reorder_geometry_event_id(preview_state),
                cache_hit=True,
                **reorder_placement_context(cached),
            )
            return cached

        log_reorder_drag_event(
            "cache.base_drag_placement.miss",
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            **reorder_geometry_cache_context(cache_key),
        )
        chip_snapshot = self._projected_chip_snapshot(
            snapshot=snapshot,
            layout_view=layout_view,
            frame=base_drag_frame,
            snapshot_kind="base_drag",
            environment=environment,
        )
        placement_snapshot = self._geometry.reorder_placement_snapshot(
            state=reorder_geometry_state(base_drag_frame.geometry),
            layout_view=layout_view,
            chip_geometry_snapshot=chip_snapshot,
            gap_ranges_by_index=snapshot.gap_ranges_by_index,
            viewport_rect=environment.viewport_rect,
            scroll_offset=environment.scroll_offset,
        )
        self._placement_cache.store(
            key=cache_key,
            snapshot=placement_snapshot,
        )
        elapsed_ms = log_reorder_drag_timing(
            "surface.reorder_base_drag_placement_snapshot",
            started_at=started_at,
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            cache_hit=False,
            **reorder_placement_context(placement_snapshot),
        )
        self._metrics.max_base_placement_ms = max(
            self._metrics.max_base_placement_ms,
            elapsed_ms,
        )
        if elapsed_ms >= _SLOW_GEOMETRY_MS:
            log_reorder_drag_event(
                "slow.placement_snapshot",
                gesture_id=reorder_geometry_gesture_id(preview_state),
                event_id=reorder_geometry_event_id(preview_state),
                elapsed_ms=f"{elapsed_ms:.3f}",
                threshold_ms=f"{_SLOW_GEOMETRY_MS:.3f}",
                **reorder_placement_context(placement_snapshot),
            )
        duplicate_targets = duplicate_reorder_placement_targets(placement_snapshot)
        if duplicate_targets:
            log_reorder_drag_event(
                "anomaly.placement_duplicate_target",
                gesture_id=reorder_geometry_gesture_id(preview_state),
                event_id=reorder_geometry_event_id(preview_state),
                duplicate_target_count=len(duplicate_targets),
                duplicate_targets=";".join(duplicate_targets),
                placement_count=len(placement_snapshot.placements),
            )
        return placement_snapshot

    def live_placement_snapshot(
        self,
        *,
        layout_view: PromptReorderLayoutView,
        chip_geometry_snapshot: PromptReorderChipGeometrySnapshot,
        gap_ranges_by_index: dict[int, tuple[int, int]],
    ) -> PromptReorderPlacementSnapshot:
        """Build placements from the already-current live prepared frame."""

        environment = self._environment("reorder_live_placement")
        return self._geometry.reorder_placement_snapshot(
            state=reorder_geometry_state(environment.live_frame.geometry),
            layout_view=layout_view,
            chip_geometry_snapshot=chip_geometry_snapshot,
            gap_ranges_by_index=gap_ranges_by_index,
            viewport_rect=environment.viewport_rect,
            scroll_offset=environment.scroll_offset,
        )

    def _projected_chip_snapshot(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        frame: PromptProjectionPreparedFrame | None,
        snapshot_kind: _SnapshotKind,
        environment: PromptReorderGeometryEnvironment | None = None,
    ) -> PromptReorderChipGeometrySnapshot:
        """Build or reuse preview/base geometry through one shared algorithm."""

        if environment is None:
            environment = self._environment(
                f"reorder_{snapshot_kind}_chip_geometry" if frame is not None else ""
            )
        if frame is None:
            return self._empty_chip_snapshot(environment)
        started_at = reorder_drag_started_at()
        cache_key = self._chip_key(
            snapshot=snapshot,
            layout_view=layout_view,
            frame=frame,
            environment=environment,
        )
        preview_state = self._preview_projection.preview_state
        cached = (
            self._chip_cache.preview(cache_key)
            if snapshot_kind == "preview"
            else self._chip_cache.base_drag(cache_key)
        )
        if cached is not None:
            self._log_chip_cache_hit(
                snapshot_kind=snapshot_kind,
                cache_key=cache_key,
                snapshot=cached,
                started_at=started_at,
            )
            return cached

        log_reorder_drag_event(
            f"cache.{snapshot_kind}_chip_geometry.miss",
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            **reorder_geometry_cache_context(cache_key),
        )
        scroll_candidate = (
            self._chip_cache.preview_scroll_candidate(cache_key)
            if snapshot_kind == "preview"
            else self._chip_cache.base_drag_scroll_candidate(cache_key)
        )
        if scroll_candidate is None:
            chip_snapshot = self._geometry.reorder_chip_geometry_snapshot(
                state=reorder_geometry_state(frame.geometry),
                layout_view=layout_view,
                chip_rendered_ranges_by_index=snapshot.chip_rendered_ranges_by_index,
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                viewport_rect=environment.viewport_rect,
                scroll_offset=environment.scroll_offset,
            )
            if snapshot_kind == "preview":
                (
                    chip_snapshot,
                    reused_chip_count,
                    rebuilt_chip_count,
                    reuse_rejected_count,
                ) = self._chip_cache.reuse_preview_geometries(chip_snapshot)
            else:
                reused_chip_count = 0
                rebuilt_chip_count = len(chip_snapshot.geometries_by_chip_index)
                reuse_rejected_count = 0
        else:
            previous_key, previous_snapshot = scroll_candidate
            scroll_result = build_reorder_geometry_after_scroll(
                self._geometry,
                reorder_geometry_state(frame.geometry),
                layout_view=layout_view,
                chip_rendered_ranges_by_index=snapshot.chip_rendered_ranges_by_index,
                chip_owned_ranges_by_index=snapshot.chip_owned_ranges_by_index,
                previous_snapshot=previous_snapshot,
                previous_viewport_rect=reorder_geometry_viewport_rect(
                    previous_key.viewport
                ),
                current_viewport_rect=environment.viewport_rect,
                current_scroll_offset=environment.scroll_offset,
            )
            chip_snapshot = scroll_result.snapshot
            reused_chip_count = scroll_result.translated_chip_count
            rebuilt_chip_count = scroll_result.rebuilt_chip_count
            reuse_rejected_count = 0
            self._metrics.record_scroll_reuse(
                translated_chip_count=reused_chip_count,
                rebuilt_chip_count=rebuilt_chip_count,
            )
        if snapshot_kind == "preview":
            self._log_preview_reuse(
                cache_key=cache_key,
                reused_chip_count=reused_chip_count,
                rebuilt_chip_count=rebuilt_chip_count,
                reuse_rejected_count=reuse_rejected_count,
            )
            self._chip_cache.store_preview(
                key=cache_key,
                snapshot=chip_snapshot,
            )
        else:
            self._chip_cache.store_base_drag(
                key=cache_key,
                snapshot=chip_snapshot,
            )
        elapsed_ms = log_reorder_drag_timing(
            f"surface.reorder_{snapshot_kind}_chip_geometry_snapshot",
            started_at=started_at,
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            reason=reorder_geometry_reason(preview_state),
            cache_hit=False,
            **chip_geometry_snapshot_context(chip_snapshot),
        )
        if snapshot_kind == "preview":
            self._metrics.max_preview_chip_ms = max(
                self._metrics.max_preview_chip_ms,
                elapsed_ms,
            )
        else:
            self._metrics.max_base_chip_ms = max(
                self._metrics.max_base_chip_ms,
                elapsed_ms,
            )
        self._log_slow_chip_snapshot(
            elapsed_ms,
            snapshot=chip_snapshot,
            snapshot_kind=snapshot_kind,
        )
        return chip_snapshot

    def _chip_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        frame: PromptProjectionPreparedFrame,
        environment: PromptReorderGeometryEnvironment,
    ) -> PromptReorderChipGeometryCacheKey:
        """Return complete identity for one chip-geometry snapshot."""

        return reorder_chip_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout_identity=id(frame),
            viewport_rect=environment.viewport_rect,
            scroll_offset=environment.scroll_offset,
            layout_width=environment.layout_width,
        )

    def _placement_key(
        self,
        *,
        snapshot: ReorderGeometrySnapshot,
        layout_view: PromptReorderLayoutView,
        frame: PromptProjectionPreparedFrame,
        environment: PromptReorderGeometryEnvironment,
    ) -> PromptReorderPlacementGeometryCacheKey:
        """Return complete identity for one placement snapshot."""

        return reorder_placement_geometry_cache_key(
            snapshot=snapshot,
            layout_view=layout_view,
            projection_layout_identity=id(frame),
            viewport_rect=environment.viewport_rect,
            scroll_offset=environment.scroll_offset,
            layout_width=environment.layout_width,
        )

    def _log_chip_cache_hit(
        self,
        *,
        snapshot_kind: _SnapshotKind,
        cache_key: PromptReorderChipGeometryCacheKey,
        snapshot: PromptReorderChipGeometrySnapshot,
        started_at: float,
    ) -> None:
        """Record one cache hit without rebuilding prompt geometry."""

        preview_state = self._preview_projection.preview_state
        log_reorder_drag_event(
            f"cache.{snapshot_kind}_chip_geometry.hit",
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            **reorder_geometry_cache_context(cache_key),
        )
        if snapshot_kind == "preview":
            self._log_preview_reuse(
                cache_key=cache_key,
                reused_chip_count=len(snapshot.geometries_by_chip_index),
                rebuilt_chip_count=0,
                reuse_rejected_count=0,
                cache_hit=True,
            )
        log_reorder_drag_timing(
            f"surface.reorder_{snapshot_kind}_chip_geometry_snapshot",
            started_at=started_at,
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            reason=reorder_geometry_reason(preview_state),
            cache_hit=True,
            **chip_geometry_snapshot_context(snapshot),
        )

    def _log_preview_reuse(
        self,
        *,
        cache_key: PromptReorderChipGeometryCacheKey,
        reused_chip_count: int,
        rebuilt_chip_count: int,
        reuse_rejected_count: int,
        cache_hit: bool = False,
    ) -> None:
        """Record preview immutable-object reuse and rejection counts."""

        preview_state = self._preview_projection.preview_state
        context = {
            "gesture_id": reorder_geometry_gesture_id(preview_state),
            "event_id": reorder_geometry_event_id(preview_state),
            "reused_chip_count": reused_chip_count,
            "rebuilt_chip_count": rebuilt_chip_count,
            "reuse_rejected_count": reuse_rejected_count,
            "cache_hit": cache_hit,
            **reorder_geometry_cache_context(cache_key),
        }
        log_reorder_drag_event("preview_geometry.reused_chip_count", **context)
        if cache_hit:
            return
        log_reorder_drag_event("preview_geometry.rebuilt_chip_count", **context)
        if reuse_rejected_count:
            log_reorder_drag_event("preview_geometry.reuse_rejected", **context)

    def _log_slow_chip_snapshot(
        self,
        elapsed_ms: float,
        *,
        snapshot: PromptReorderChipGeometrySnapshot,
        snapshot_kind: str,
    ) -> None:
        """Record unexpectedly slow geometry construction."""

        if elapsed_ms < _SLOW_GEOMETRY_MS:
            return
        preview_state = self._preview_projection.preview_state
        log_reorder_drag_event(
            "slow.chip_geometry_snapshot",
            gesture_id=reorder_geometry_gesture_id(preview_state),
            event_id=reorder_geometry_event_id(preview_state),
            elapsed_ms=f"{elapsed_ms:.3f}",
            threshold_ms=f"{_SLOW_GEOMETRY_MS:.3f}",
            snapshot_kind=snapshot_kind,
            **chip_geometry_snapshot_context(snapshot),
        )

    @staticmethod
    def _empty_chip_snapshot(
        environment: PromptReorderGeometryEnvironment,
    ) -> PromptReorderChipGeometrySnapshot:
        """Return empty geometry preserving current viewport values."""

        return PromptReorderChipGeometrySnapshot(
            geometries_by_chip_index={},
            ordered_chip_indices=(),
            visual_line_count=0,
            layout_width=environment.viewport_rect.width(),
            content_height=0.0,
            scroll_offset=environment.scroll_offset,
        )

    @staticmethod
    def _empty_placement_snapshot(
        environment: PromptReorderGeometryEnvironment,
    ) -> PromptReorderPlacementSnapshot:
        """Return empty placement geometry preserving current viewport width."""

        return PromptReorderPlacementSnapshot(
            placements=(),
            visual_line_count=0,
            layout_width=environment.viewport_rect.width(),
            content_height=0.0,
        )


__all__ = [
    "PromptReorderGeometryEnvironment",
    "PromptReorderGeometryOwner",
]
