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

"""Own revisioned live reorder chip geometry and adapted visual publication."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from substitute.application.prompt_editor.document.views import PromptReorderChipView

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.observability import reorder_drag_started_at
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
    chip_geometry_snapshot_context,
)
from ..projection.reorder_interaction_geometry import PromptReorderInteractionGeometry
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_state import (
    ReorderLiveVisualGeometryKey,
)
from .chip_visuals import PromptChipVisual
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_visual_cache import PromptReorderChipVisualSnapshot
from .reorder_visual_geometry import prompt_reorder_visual_for_chip_geometry

_SLOW_LIVE_VISUALS_MS = 8.0
_EMPTY_VISUALS: Mapping[int, PromptChipVisual] = MappingProxyType({})
_EMPTY_VISUAL_SNAPSHOTS: Mapping[int, PromptReorderChipVisualSnapshot] = (
    MappingProxyType({})
)
_EMPTY_OWNED_RANGES: Mapping[int, tuple[tuple[int, int], ...]] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class PromptReorderLiveVisualPublication:
    """Publish one coherent live geometry generation and its adapted visuals."""

    revision: int
    geometry_key: ReorderLiveVisualGeometryKey | None
    chip_geometry: PromptReorderChipGeometrySnapshot | None
    visuals_by_index: Mapping[int, PromptChipVisual]
    visual_snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot]
    owned_ranges_by_index: Mapping[int, tuple[tuple[int, int], ...]]


@dataclass(frozen=True, slots=True)
class PromptReorderLiveVisualOutcome:
    """Report whether one live visual request rebuilt its publication."""

    publication: PromptReorderLiveVisualPublication
    rebuilt: bool


class PromptReorderLiveVisualOwner:
    """Prepare live chip visuals once per complete bounded geometry identity."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
    ) -> None:
        """Store focused collaborators and initialize an empty publication."""

        self._geometry = geometry
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._publication = PromptReorderLiveVisualPublication(
            revision=0,
            geometry_key=None,
            chip_geometry=None,
            visuals_by_index=_EMPTY_VISUALS,
            visual_snapshots_by_index=_EMPTY_VISUAL_SNAPSHOTS,
            owned_ranges_by_index=_EMPTY_OWNED_RANGES,
        )

    @property
    def publication(self) -> PromptReorderLiveVisualPublication:
        """Return the latest immutable live visual publication."""

        return self._publication

    @property
    def visuals_by_index(self) -> Mapping[int, PromptChipVisual]:
        """Return the current immutable live visual mapping."""

        return self._publication.visuals_by_index

    @property
    def chip_geometry(self) -> PromptReorderChipGeometrySnapshot | None:
        """Return live chip geometry from the same publication as its visuals."""

        return self._publication.chip_geometry

    @property
    def visual_snapshots_by_index(
        self,
    ) -> Mapping[int, PromptReorderChipVisualSnapshot]:
        """Return complete projection snapshots from the same publication."""

        return self._publication.visual_snapshots_by_index

    @property
    def owned_ranges_by_index(self) -> Mapping[int, tuple[tuple[int, int], ...]]:
        """Return semantic source ownership from the same publication."""

        return self._publication.owned_ranges_by_index

    def invalidate(self) -> None:
        """Force the next request to rebuild without discarding painted state."""

        publication = self._publication
        if publication.geometry_key is None:
            return
        self._publication = PromptReorderLiveVisualPublication(
            revision=publication.revision,
            geometry_key=None,
            chip_geometry=publication.chip_geometry,
            visuals_by_index=publication.visuals_by_index,
            visual_snapshots_by_index=publication.visual_snapshots_by_index,
            owned_ranges_by_index=publication.owned_ranges_by_index,
        )

    def clear(self) -> None:
        """Discard all live geometry and visuals for a closed session."""

        publication = self._publication
        self._publication = PromptReorderLiveVisualPublication(
            revision=publication.revision + 1,
            geometry_key=None,
            chip_geometry=None,
            visuals_by_index=_EMPTY_VISUALS,
            visual_snapshots_by_index=_EMPTY_VISUAL_SNAPSHOTS,
            owned_ranges_by_index=_EMPTY_OWNED_RANGES,
        )

    def prepare(
        self,
        *,
        geometry_key: ReorderLiveVisualGeometryKey,
        segments_by_index: Mapping[int, PromptReorderChipView],
        reason: str,
    ) -> PromptReorderLiveVisualOutcome:
        """Reuse or rebuild live visuals from one complete viewport identity."""

        publication = self._publication
        if geometry_key == publication.geometry_key and publication.visuals_by_index:
            self._diagnostics.log_event(
                "live_visuals.skipped_unchanged_geometry",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                reason=reason,
                visual_count=len(publication.visuals_by_index),
                cache_size=0,
            )
            return PromptReorderLiveVisualOutcome(
                publication=publication,
                rebuilt=False,
            )

        next_publication = self._build(
            geometry_key=geometry_key,
            segments_by_index=segments_by_index,
            reason=reason,
        )
        self._publication = next_publication
        return PromptReorderLiveVisualOutcome(
            publication=next_publication,
            rebuilt=True,
        )

    def _build(
        self,
        *,
        geometry_key: ReorderLiveVisualGeometryKey,
        segments_by_index: Mapping[int, PromptReorderChipView],
        reason: str,
    ) -> PromptReorderLiveVisualPublication:
        """Build and publish every live chip from projection-owned geometry."""

        total_started_at = reorder_drag_started_at()
        geometry_state: PromptReorderInteractionGeometryState = self._geometry.state
        layout_view = geometry_state.current_layout_view
        if layout_view is None:
            return PromptReorderLiveVisualPublication(
                revision=self._publication.revision + 1,
                geometry_key=geometry_key,
                chip_geometry=None,
                visuals_by_index=_EMPTY_VISUALS,
                visual_snapshots_by_index=_EMPTY_VISUAL_SNAPSHOTS,
                owned_ranges_by_index=_EMPTY_OWNED_RANGES,
            )
        rendered_ranges = {
            segment.index: (segment.selection_start, segment.selection_end)
            for segment in segments_by_index.values()
        }
        owned_ranges: dict[int, tuple[tuple[int, int], ...]] = {
            segment_index: (source_range,)
            for segment_index, source_range in rendered_ranges.items()
        }
        snapshot = self._geometry.build_live_chip_snapshot(
            layout_view=layout_view,
            chip_rendered_ranges_by_index=rendered_ranges,
            chip_owned_ranges_by_index=owned_ranges,
        )
        if len(snapshot.geometries_by_chip_index) != len(segments_by_index):
            self._diagnostics.log_anomaly(
                "anomaly.chip_geometry_paint_count_mismatch",
                expected_chip_count=len(segments_by_index),
                chip_geometry_count=len(snapshot.geometries_by_chip_index),
                **chip_geometry_snapshot_context(snapshot),
            )
        visuals = MappingProxyType(
            {
                chip_index: prompt_reorder_visual_for_chip_geometry(geometry)
                for chip_index, geometry in snapshot.geometries_by_chip_index.items()
            }
        )
        total_elapsed_ms = self._diagnostics.log_timing(
            "live_visuals.total",
            started_at=total_started_at,
            gesture_id=self._metrics.gesture_id,
            event_id=self._metrics.event_id,
            reason=reason,
            segment_count=len(segments_by_index),
            visual_count=len(visuals),
            reused_visual_count=0,
            rebuilt_visual_count=len(visuals),
            fragment_query_count=0,
            fragment_total_count=0,
            split_bubble_count=sum(
                1 for visual in visuals.values() if len(visual.bubble_rects) > 1
            ),
            slowest_segment_index=None,
            slowest_fragment_query_ms="0.000",
            **chip_geometry_snapshot_context(snapshot),
        )
        self._metrics.record_live_visuals_elapsed(total_elapsed_ms)
        self._diagnostics.log_slow_path_if_needed(
            "slow.live_visuals",
            elapsed_ms=total_elapsed_ms,
            threshold_ms=_SLOW_LIVE_VISUALS_MS,
            reason=reason,
            segment_count=len(segments_by_index),
            reused_visual_count=0,
            rebuilt_visual_count=len(visuals),
            slowest_segment_index=None,
        )
        return PromptReorderLiveVisualPublication(
            revision=self._publication.revision + 1,
            geometry_key=geometry_key,
            chip_geometry=snapshot,
            visuals_by_index=visuals,
            visual_snapshots_by_index=_EMPTY_VISUAL_SNAPSHOTS,
            owned_ranges_by_index=MappingProxyType(owned_ranges),
        )


__all__ = [
    "PromptReorderLiveVisualOutcome",
    "PromptReorderLiveVisualOwner",
    "PromptReorderLiveVisualPublication",
]
