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

"""Own one revisioned prepared-visual publication for prompt reorder chrome."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Literal

from PySide6.QtGui import QColor

from ..projection.reorder_surface_chrome import (
    PromptReorderSurfaceChromeChip,
    PromptReorderSurfaceChromeStyle,
)
from ..projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
    empty_reorder_surface_visual_publication,
)
from ..projection.reorder_visual_snapshot import (
    PromptReorderProjectionPaintSnapshot,
)
from .reorder_render_state import (
    PromptReorderChipPaintState,
    PromptReorderViewRenderInput,
    PromptReorderViewRenderState,
    prompt_reorder_view_render_state,
)

type PromptReorderPreparedVisualMode = Literal["live", "preview"]


@dataclass(frozen=True, slots=True)
class PromptReorderPreparedVisualPublication:
    """Carry every prepared value published to reorder paint surfaces."""

    revision: int
    overlay_state: PromptReorderViewRenderState
    surface: PromptReorderSurfaceVisualPublication
    unsafe_transient_indices: tuple[int, ...]


class PromptReorderPreparedVisualOwner:
    """Prepare and retain one authoritative visual publication per sync."""

    def __init__(self) -> None:
        """Initialize an empty live prepared-visual publication."""

        self._publication = PromptReorderPreparedVisualPublication(
            revision=0,
            overlay_state=PromptReorderViewRenderState(),
            surface=empty_reorder_surface_visual_publication(),
            unsafe_transient_indices=(),
        )

    @property
    def publication(self) -> PromptReorderPreparedVisualPublication:
        """Return the latest complete prepared-visual publication."""

        return self._publication

    def prepare(
        self,
        render_input: PromptReorderViewRenderInput,
    ) -> PromptReorderPreparedVisualPublication:
        """Prepare and publish one complete visual frame."""

        self._publication = _prepare_reorder_visual_publication(
            render_input,
            revision=self._publication.revision + 1,
        )
        return self._publication

    def clear(self) -> PromptReorderPreparedVisualPublication:
        """Publish an empty live visual frame."""

        self._publication = PromptReorderPreparedVisualPublication(
            revision=self._publication.revision + 1,
            overlay_state=PromptReorderViewRenderState(),
            surface=empty_reorder_surface_visual_publication(),
            unsafe_transient_indices=(),
        )
        return self._publication


def _prepare_reorder_visual_publication(
    render_input: PromptReorderViewRenderInput,
    *,
    revision: int,
) -> PromptReorderPreparedVisualPublication:
    """Prepare overlay and surface paint ownership as one publication."""

    state = prompt_reorder_view_render_state(render_input)
    active_chips = state.preview_chips if state.preview_active else state.live_chips
    surface_chips = tuple(
        _surface_chrome_chip(chip)
        for chip in active_chips
        if chip.geometry is not None and not chip.owns_projection_text
    )
    overlay_chips = tuple(chip for chip in active_chips if chip.owns_projection_text)
    unsafe_indices = tuple(
        chip.segment_index
        for chip in active_chips
        if chip.geometry is None and not chip.owns_projection_text
    )
    overlay_state = replace(
        state,
        live_chips=overlay_chips if not state.preview_active else (),
        preview_chips=overlay_chips if state.preview_active else (),
        raster_paint_count=sum(1 for chip in overlay_chips if chip.raster_entry),
    )
    return PromptReorderPreparedVisualPublication(
        revision=revision,
        overlay_state=overlay_state,
        surface=PromptReorderSurfaceVisualPublication(
            mode="preview" if state.preview_active else "live",
            chips=surface_chips,
            suppression_snapshots_by_index=MappingProxyType(
                _suppression_snapshots(render_input, state)
            ),
        ),
        unsafe_transient_indices=unsafe_indices,
    )


def _suppression_snapshots(
    render_input: PromptReorderViewRenderInput,
    state: PromptReorderViewRenderState,
) -> dict[int, PromptReorderProjectionPaintSnapshot]:
    """Return exact projection snapshots replaced by complete overlay paint."""

    if not state.preview_active:
        return {}
    snapshots_by_index = {
        chip.segment_index: chip.visual_snapshot.projection_snapshot
        for chip in state.preview_chips
        if chip.owns_projection_text and chip.visual_snapshot is not None
    }
    dragged_segment_index = state.dragged_segment_index
    dragged_snapshot = (
        None
        if dragged_segment_index is None
        else render_input.preview_visual_snapshots_by_index.get(dragged_segment_index)
    )
    if (
        dragged_segment_index is not None
        and dragged_snapshot is not None
        and dragged_snapshot.projection_snapshot.fragments
    ):
        snapshots_by_index[dragged_segment_index] = dragged_snapshot.projection_snapshot
    return snapshots_by_index


def _surface_chrome_chip(
    chip: PromptReorderChipPaintState,
) -> PromptReorderSurfaceChromeChip:
    """Convert one stationary prepared item into surface-owned chrome."""

    geometry = chip.geometry
    if geometry is None:
        raise ValueError("Surface chrome requires projection-owned chip geometry.")
    style = chip.style
    return PromptReorderSurfaceChromeChip(
        segment_index=chip.segment_index,
        geometry=geometry,
        style=PromptReorderSurfaceChromeStyle(
            fill_color=QColor(style.fill_color),
            border_color=QColor(style.border_color),
            outline_only=style.outline_only,
            outline_width=style.outline_width,
            opacity=style.opacity,
        ),
    )


__all__ = [
    "PromptReorderPreparedVisualMode",
    "PromptReorderPreparedVisualOwner",
    "PromptReorderPreparedVisualPublication",
]
