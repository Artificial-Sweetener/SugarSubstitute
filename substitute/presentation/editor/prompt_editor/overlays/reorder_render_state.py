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

"""Prepare immutable prompt reorder paint state from published visual inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from .chip_painter import PromptChipPaintStyle
from .chip_visuals import PromptChipVisual
from .reorder_raster_cache import ReorderRasterEntry
from .reorder_visual_cache import PromptReorderChipVisualSnapshot
from .reorder_visual_geometry import (
    prompt_reorder_visual_for_chip_geometry,
    reorder_visual_translated_to_hotspot_rect,
)
from .reorder_visual_style import PromptReorderVisualStyle


@dataclass(frozen=True, slots=True)
class PromptReorderChipPaintState:
    """Describe one prepared reorder chip chrome item to paint."""

    segment_index: int
    style: PromptChipPaintStyle
    geometry: PromptReorderChipGeometry | None = None
    visual: PromptChipVisual | None = None
    visual_snapshot: PromptReorderChipVisualSnapshot | None = None
    raster_entry: ReorderRasterEntry | None = None

    @property
    def owns_projection_text(self) -> bool:
        """Return whether this state can replace surface-painted chip text."""

        return self.visual is not None and (
            self.visual_snapshot is not None
            and bool(self.visual_snapshot.projection_snapshot.fragments)
        )


@dataclass(frozen=True, slots=True)
class PromptReorderMarkerPaintState:
    """Describe one prepared insertion marker to paint."""

    rect: QRectF
    color: QColor


@dataclass(frozen=True, slots=True)
class PromptReorderLandingPreviewPaintState:
    """Describe one prepared landing preview or pending shadow to paint."""

    style: PromptChipPaintStyle
    geometry: PromptReorderChipGeometry | None = None
    visual: PromptChipVisual | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderViewRenderState:
    """Describe all prepared chrome needed by the passive reorder view."""

    preview_active: bool = False
    live_chips: tuple[PromptReorderChipPaintState, ...] = ()
    preview_chips: tuple[PromptReorderChipPaintState, ...] = ()
    marker: PromptReorderMarkerPaintState | None = None
    landing_preview: PromptReorderLandingPreviewPaintState | None = None
    gesture_id: int | None = None
    event_id: int | None = None
    dragged_segment_index: int | None = None
    raster_paint_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderViewRenderInput:
    """Carry prepared overlay state needed to build passive render state."""

    visual_style: PromptReorderVisualStyle
    preview_active: bool
    live_ordered_segment_indices: Sequence[int]
    preview_ordered_segment_indices: Sequence[int]
    live_geometries_by_index: Mapping[int, PromptReorderChipGeometry]
    preview_geometries_by_index: Mapping[int, PromptReorderChipGeometry]
    live_visuals_by_index: Mapping[int, PromptChipVisual]
    preview_visuals_by_index: Mapping[int, PromptChipVisual]
    dragged_segment_index: int | None
    hovered_segment_index: int | None
    active_segment_index: int | None
    live_visual_snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot] = (
        field(default_factory=dict)
    )
    preview_visual_snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot] = (
        field(default_factory=dict)
    )
    live_raster_entries_by_index: Mapping[int, ReorderRasterEntry] = field(
        default_factory=dict
    )
    preview_raster_entries_by_index: Mapping[int, ReorderRasterEntry] = field(
        default_factory=dict
    )
    marker_rect: QRectF | None = None
    landing_preview: PromptReorderLandingPreviewPaintState | None = None
    gesture_id: int | None = None
    event_id: int | None = None
    paint_rect_overrides_by_index: Mapping[int, QRectF] = field(default_factory=dict)


def prompt_reorder_chip_paint_states(
    segment_indices: Sequence[int],
    *,
    geometries_by_index: Mapping[int, PromptReorderChipGeometry],
    visuals_by_index: Mapping[int, PromptChipVisual],
    visual_snapshots_by_index: (
        Mapping[int, PromptReorderChipVisualSnapshot] | None
    ) = None,
    raster_entries_by_index: Mapping[int, ReorderRasterEntry] | None = None,
    paint_rect_overrides_by_index: Mapping[int, QRectF] | None = None,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    skip_dragged_segment: bool,
) -> tuple[PromptReorderChipPaintState, ...]:
    """Build prepared chip paint state from projection geometry and visuals."""

    states: list[PromptReorderChipPaintState] = []
    paint_rect_overrides = paint_rect_overrides_by_index or {}
    visual_snapshots = visual_snapshots_by_index or {}
    raster_entries = raster_entries_by_index or {}
    for segment_index in segment_indices:
        if skip_dragged_segment and segment_index == dragged_segment_index:
            continue
        geometry = geometries_by_index.get(segment_index)
        visual = visuals_by_index.get(segment_index)
        visual_snapshot = visual_snapshots.get(segment_index)
        paint_rect_override = paint_rect_overrides.get(segment_index)
        if paint_rect_override is not None:
            visual = reorder_visual_translated_to_hotspot_rect(
                visual
                if visual is not None
                else (
                    None
                    if geometry is None
                    else prompt_reorder_visual_for_chip_geometry(geometry)
                ),
                paint_rect_override,
            )
            geometry = None
        if geometry is None and visual is None:
            continue
        states.append(
            PromptReorderChipPaintState(
                segment_index=segment_index,
                geometry=geometry,
                visual=visual,
                visual_snapshot=visual_snapshot,
                raster_entry=raster_entries.get(segment_index),
                style=visual_style.paint_style_for_segment(
                    segment_index,
                    dragged_segment_index=dragged_segment_index,
                    hovered_segment_index=hovered_segment_index,
                    active_segment_index=active_segment_index,
                ),
            )
        )
    return tuple(states)


def prompt_reorder_marker_paint_state(
    marker_rect: QRectF | None,
    *,
    visual_style: PromptReorderVisualStyle,
) -> PromptReorderMarkerPaintState | None:
    """Build prepared insertion-marker paint state from a resolved marker rect."""

    if marker_rect is None:
        return None
    return PromptReorderMarkerPaintState(
        rect=QRectF(marker_rect),
        color=QColor(visual_style.marker_color),
    )


def prompt_reorder_view_render_state(
    render_input: PromptReorderViewRenderInput,
) -> PromptReorderViewRenderState:
    """Build all prepared reorder paint state for the passive overlay view."""

    preview_chips = (
        prompt_reorder_chip_paint_states(
            render_input.preview_ordered_segment_indices,
            geometries_by_index=render_input.preview_geometries_by_index,
            visuals_by_index=render_input.preview_visuals_by_index,
            visual_snapshots_by_index=render_input.preview_visual_snapshots_by_index,
            raster_entries_by_index=render_input.preview_raster_entries_by_index,
            paint_rect_overrides_by_index=render_input.paint_rect_overrides_by_index,
            visual_style=render_input.visual_style,
            dragged_segment_index=render_input.dragged_segment_index,
            hovered_segment_index=render_input.hovered_segment_index,
            active_segment_index=render_input.active_segment_index,
            skip_dragged_segment=True,
        )
        if render_input.preview_active
        else ()
    )
    live_chips = (
        ()
        if render_input.preview_active
        else prompt_reorder_chip_paint_states(
            render_input.live_ordered_segment_indices,
            geometries_by_index=render_input.live_geometries_by_index,
            visuals_by_index=render_input.live_visuals_by_index,
            visual_snapshots_by_index=render_input.live_visual_snapshots_by_index,
            raster_entries_by_index=render_input.live_raster_entries_by_index,
            paint_rect_overrides_by_index=render_input.paint_rect_overrides_by_index,
            visual_style=render_input.visual_style,
            dragged_segment_index=render_input.dragged_segment_index,
            hovered_segment_index=render_input.hovered_segment_index,
            active_segment_index=render_input.active_segment_index,
            skip_dragged_segment=False,
        )
    )
    painted_chips = preview_chips if render_input.preview_active else live_chips
    return PromptReorderViewRenderState(
        preview_active=render_input.preview_active,
        live_chips=live_chips,
        preview_chips=preview_chips,
        marker=prompt_reorder_marker_paint_state(
            render_input.marker_rect,
            visual_style=render_input.visual_style,
        ),
        landing_preview=render_input.landing_preview,
        gesture_id=render_input.gesture_id,
        event_id=render_input.event_id,
        dragged_segment_index=render_input.dragged_segment_index,
        raster_paint_count=sum(1 for chip in painted_chips if chip.raster_entry),
    )


__all__ = [
    "PromptReorderChipPaintState",
    "PromptReorderLandingPreviewPaintState",
    "PromptReorderMarkerPaintState",
    "PromptReorderViewRenderInput",
    "PromptReorderViewRenderState",
    "prompt_reorder_chip_paint_states",
    "prompt_reorder_marker_paint_state",
    "prompt_reorder_view_render_state",
]
