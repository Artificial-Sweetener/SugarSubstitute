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

"""Publish synchronized reorder drop geometry with structural diagnostics."""

from __future__ import annotations

from .observability import log_reorder_drag_event
from .reorder_drop_geometry_builder import (
    PromptReorderDropGeometry,
    build_reorder_drop_geometry,
)
from .reorder_drop_targets import PromptReorderRowDropLane
from .reorder_placement_geometry import PromptReorderPlacementSnapshot


class PromptReorderDropGeometryPublisher:
    """Build one drop-geometry publication and report its bounded structure."""

    def publish(
        self,
        snapshot: PromptReorderPlacementSnapshot,
        *,
        gesture_id: int | None,
        event_id: int | None,
    ) -> PromptReorderDropGeometry:
        """Return prepared placements, target visuals, and lanes together."""

        publication = build_reorder_drop_geometry(snapshot)
        row_lane_count = sum(
            isinstance(lane, PromptReorderRowDropLane) for lane in publication.lanes
        )
        log_reorder_drag_event(
            "placement_geometry.snapshot",
            gesture_id=gesture_id,
            event_id=event_id,
            placement_count=len(publication.placement_snapshot.placements),
            row_lane_count=row_lane_count,
            blank_lane_count=len(publication.lanes) - row_lane_count,
            visual_line_count=publication.placement_snapshot.visual_line_count,
            layout_width=(f"{publication.placement_snapshot.layout_width:.2f}"),
            content_height=(f"{publication.placement_snapshot.content_height:.2f}"),
        )
        return publication


__all__ = ["PromptReorderDropGeometryPublisher"]
