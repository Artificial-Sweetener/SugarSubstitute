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

"""Own prepared preview visuals for one reorder geometry publication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from substitute.application.prompt_editor.reorder.views import (
    PromptReorderDropTarget,
)

from ..projection.observability import (
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from ..projection.reorder_chip_geometry import (
    PromptReorderChipGeometrySnapshot,
    chip_geometry_snapshot_context,
)
from ..projection.reorder_chip_visual_identity import (
    chip_geometry_visual_reuse_key,
)
from ..projection.reorder_preview_geometry_transition import (
    PromptReorderGeometryRefresh,
)
from ..projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from ..projection.reorder_state import PromptReorderOverlayPositionGeometryKey
from .chip_visuals import PromptChipVisual
from .reorder_visual_geometry import prompt_reorder_visual_for_chip_geometry

_EMPTY_VISUALS: Mapping[int, PromptChipVisual] = MappingProxyType({})


@dataclass(frozen=True, slots=True, eq=False)
class PromptReorderPreviewVisualKey:
    """Identify all inputs that can change prepared preview visuals."""

    preview_snapshot: object | None
    base_drag_snapshot: object | None
    preview_layout: object | None
    base_drag_layout: object | None
    dragged_segment_index: int | None
    active_target: PromptReorderDropTarget | None
    viewport_identity: PromptReorderOverlayPositionGeometryKey

    def matches(self, other: PromptReorderPreviewVisualKey) -> bool:
        """Compare publication sources by identity and bounded scalar values."""

        return (
            self.matches_except_viewport(other)
            and self.viewport_identity == other.viewport_identity
        )

    def matches_except_viewport(self, other: PromptReorderPreviewVisualKey) -> bool:
        """Compare every non-viewport input without hashing nested prompt state."""

        return (
            self.preview_snapshot is other.preview_snapshot
            and self.base_drag_snapshot is other.base_drag_snapshot
            and self.preview_layout is other.preview_layout
            and self.base_drag_layout is other.base_drag_layout
            and self.dragged_segment_index == other.dragged_segment_index
            and self.active_target == other.active_target
        )


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewVisualMetrics:
    """Count structural preview preparation work for regression evidence."""

    full_build_count: int = 0
    unchanged_reuse_count: int = 0
    geometry_free_height_reuse_count: int = 0
    reused_chip_count: int = 0
    rebuilt_chip_count: int = 0
    reuse_rejected_count: int = 0
    base_drag_geometry_reuse_count: int = 0
    base_drag_geometry_rebuild_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewVisualPublication:
    """Publish one coherent geometry generation and its adapted visuals."""

    key: PromptReorderPreviewVisualKey
    geometry: PromptReorderGeometryRefresh
    visuals_by_index: Mapping[int, PromptChipVisual]


@dataclass(frozen=True, slots=True)
class PromptReorderPreviewVisualOutcome:
    """Describe one prepared-preview request without exposing mutable storage."""

    publication: PromptReorderPreviewVisualPublication
    rebuilt: bool
    reused_chip_count: int
    rebuilt_chip_count: int
    reuse_rejected_count: int


class PromptReorderPreviewVisualOwner:
    """Publish preview geometry and visuals once per complete input identity."""

    def __init__(
        self,
        *,
        geometry_state: Callable[[], PromptReorderInteractionGeometryState],
        refresh_preview_geometry: Callable[..., PromptReorderGeometryRefresh],
    ) -> None:
        """Store the lower geometry owner and initialize empty publication state."""

        self._geometry_state = geometry_state
        self._refresh_preview_geometry = refresh_preview_geometry
        self._publication: PromptReorderPreviewVisualPublication | None = None
        self._metrics = PromptReorderPreviewVisualMetrics()

    @property
    def publication(self) -> PromptReorderPreviewVisualPublication | None:
        """Return the latest complete preview visual publication."""

        return self._publication

    @property
    def metrics(self) -> PromptReorderPreviewVisualMetrics:
        """Return immutable structural counters for focused diagnostics."""

        return self._metrics

    @property
    def visuals_by_index(self) -> Mapping[int, PromptChipVisual]:
        """Return prepared preview visuals or one shared empty mapping."""

        if self._publication is None:
            return _EMPTY_VISUALS
        return self._publication.visuals_by_index

    def clear(self) -> None:
        """Discard the prepared preview publication."""

        self._publication = None

    def reset_metrics(self) -> None:
        """Reset structural counters without changing the publication."""

        self._metrics = PromptReorderPreviewVisualMetrics()

    def prepare(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: PromptReorderOverlayPositionGeometryKey,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderPreviewVisualOutcome:
        """Return a reused or newly prepared preview visual publication."""

        key = self._key(
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
        )
        publication = self._publication
        if publication is not None and publication.key.matches(key):
            self._metrics = replace(
                self._metrics,
                unchanged_reuse_count=self._metrics.unchanged_reuse_count + 1,
            )
            return PromptReorderPreviewVisualOutcome(
                publication=publication,
                rebuilt=False,
                reused_chip_count=0,
                rebuilt_chip_count=0,
                reuse_rejected_count=0,
            )
        if publication is not None and _can_reuse_geometry_free_height_change(
            publication,
            key,
        ):
            publication = replace(publication, key=key)
            self._publication = publication
            self._metrics = replace(
                self._metrics,
                geometry_free_height_reuse_count=(
                    self._metrics.geometry_free_height_reuse_count + 1
                ),
            )
            return PromptReorderPreviewVisualOutcome(
                publication=publication,
                rebuilt=False,
                reused_chip_count=0,
                rebuilt_chip_count=0,
                reuse_rejected_count=0,
            )

        started_at = reorder_drag_started_at()
        previous_geometry = None if publication is None else publication.geometry
        previous_visuals: Mapping[int, PromptChipVisual] = (
            {} if publication is None else publication.visuals_by_index
        )
        refresh = self._refresh_preview_geometry(
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
            gesture_id=gesture_id,
            event_id=event_id,
        )
        visuals, reused, rebuilt, rejected = _adapt_preview_visuals(
            refresh.preview_chip_snapshot,
            previous_snapshot=(
                None
                if previous_geometry is None
                else previous_geometry.preview_chip_snapshot
            ),
            previous_visuals=previous_visuals,
        )
        publication = PromptReorderPreviewVisualPublication(
            key=key,
            geometry=refresh,
            visuals_by_index=MappingProxyType(visuals),
        )
        self._publication = publication
        self._metrics = PromptReorderPreviewVisualMetrics(
            full_build_count=self._metrics.full_build_count + 1,
            unchanged_reuse_count=self._metrics.unchanged_reuse_count,
            geometry_free_height_reuse_count=(
                self._metrics.geometry_free_height_reuse_count
            ),
            reused_chip_count=self._metrics.reused_chip_count + reused,
            rebuilt_chip_count=self._metrics.rebuilt_chip_count + rebuilt,
            reuse_rejected_count=self._metrics.reuse_rejected_count + rejected,
            base_drag_geometry_reuse_count=(
                self._metrics.base_drag_geometry_reuse_count
                + int(refresh.base_drag_geometry_reused)
            ),
            base_drag_geometry_rebuild_count=(
                self._metrics.base_drag_geometry_rebuild_count
                + int(refresh.base_drag_geometry_rebuilt)
            ),
        )
        log_reorder_drag_timing(
            "preview_visual_owner.prepare",
            started_at=started_at,
            gesture_id=gesture_id,
            event_id=event_id,
            visual_count=len(visuals),
            reused_visual_count=reused,
            rebuilt_visual_count=rebuilt,
            reuse_rejected_count=rejected,
            **(
                {}
                if refresh.preview_chip_snapshot is None
                else chip_geometry_snapshot_context(refresh.preview_chip_snapshot)
            ),
        )
        return PromptReorderPreviewVisualOutcome(
            publication=publication,
            rebuilt=True,
            reused_chip_count=reused,
            rebuilt_chip_count=rebuilt,
            reuse_rejected_count=rejected,
        )

    def _key(
        self,
        *,
        dragged_segment_index: int | None,
        active_target: PromptReorderDropTarget | None,
        viewport_identity: PromptReorderOverlayPositionGeometryKey,
    ) -> PromptReorderPreviewVisualKey:
        """Build a constant-work identity from immutable publication references."""

        state = self._geometry_state()
        return PromptReorderPreviewVisualKey(
            preview_snapshot=state.preview_snapshot,
            base_drag_snapshot=state.base_drag_snapshot,
            preview_layout=state.preview_layout_view,
            base_drag_layout=state.base_drag_layout_view,
            dragged_segment_index=dragged_segment_index,
            active_target=active_target,
            viewport_identity=viewport_identity,
        )


def _adapt_preview_visuals(
    snapshot: PromptReorderChipGeometrySnapshot | None,
    *,
    previous_snapshot: PromptReorderChipGeometrySnapshot | None,
    previous_visuals: Mapping[int, PromptChipVisual],
) -> tuple[dict[int, PromptChipVisual], int, int, int]:
    """Adapt chip geometry while reusing visuals with identical geometry."""

    if snapshot is None:
        return {}, 0, 0, int(bool(previous_visuals))
    previous_geometries = (
        {} if previous_snapshot is None else previous_snapshot.geometries_by_chip_index
    )
    visuals: dict[int, PromptChipVisual] = {}
    reused = 0
    rebuilt = 0
    rejected = 0
    for chip_index, geometry in snapshot.geometries_by_chip_index.items():
        previous_geometry = previous_geometries.get(chip_index)
        previous_visual = previous_visuals.get(chip_index)
        if (
            previous_geometry is not None
            and previous_visual is not None
            and chip_geometry_visual_reuse_key(previous_geometry)
            == chip_geometry_visual_reuse_key(geometry)
        ):
            visuals[chip_index] = previous_visual
            reused += 1
            continue
        if previous_geometry is not None or previous_visual is not None:
            rejected += 1
        visuals[chip_index] = prompt_reorder_visual_for_chip_geometry(geometry)
        rebuilt += 1
    return visuals, reused, rebuilt, rejected


def _can_reuse_geometry_free_height_change(
    publication: PromptReorderPreviewVisualPublication,
    key: PromptReorderPreviewVisualKey,
) -> bool:
    """Reuse an empty geometry generation across a height-only viewport change."""

    geometry = publication.geometry
    return (
        publication.key.matches_except_viewport(key)
        and _viewport_change_is_height_only(
            publication.key.viewport_identity,
            key.viewport_identity,
        )
        and geometry.previous_preview_chip_snapshot is None
        and geometry.preview_chip_snapshot is None
        and geometry.base_drag_chip_snapshot is None
        and geometry.placement_snapshot is None
        and not geometry.drop_target_visuals
        and not geometry.drop_target_lanes
        and geometry.preview_geometry_identity is None
        and not publication.visuals_by_index
    )


def _viewport_change_is_height_only(
    previous: PromptReorderOverlayPositionGeometryKey,
    current: PromptReorderOverlayPositionGeometryKey,
) -> bool:
    """Return whether only viewport and content height changed."""

    return (
        previous != current
        and replace(
            previous,
            viewport_height=current.viewport_height,
            content_height=current.content_height,
        )
        == current
    )


__all__ = [
    "PromptReorderPreviewVisualKey",
    "PromptReorderPreviewVisualMetrics",
    "PromptReorderPreviewVisualOutcome",
    "PromptReorderPreviewVisualOwner",
    "PromptReorderPreviewVisualPublication",
]
