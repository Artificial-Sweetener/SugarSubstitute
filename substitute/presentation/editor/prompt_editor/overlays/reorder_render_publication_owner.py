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

"""Own atomic reorder render preparation and outward publication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from ..projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)
from .chip_painter import PromptChipPaintStyle
from .reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_insertion_marker_owner import PromptReorderInsertionMarkerOwner
from .reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from .reorder_landing_models import PromptReorderLandingShadowRequest
from .reorder_landing_request_owner import PromptReorderLandingRequestOwner
from .reorder_landing_paint import PromptReorderLandingPaintOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_prepared_visual import (
    PromptReorderPreparedVisualOwner,
    PromptReorderPreparedVisualPublication,
)
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_raster_cache import ReorderRasterEntry
from .reorder_raster_publication import PromptReorderRasterPublicationOwner
from .reorder_render_state import (
    PromptReorderViewRenderInput,
    PromptReorderViewRenderState,
)
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_style import PromptReorderVisualStyle

_EMPTY_GEOMETRIES: Mapping[int, PromptReorderChipGeometry] = MappingProxyType({})
_EMPTY_RASTERS: Mapping[int, ReorderRasterEntry] = MappingProxyType({})


class PromptReorderRenderPublicationOwner:
    """Prepare and publish one coherent reorder frame from owner snapshots."""

    def __init__(
        self,
        *,
        geometry: PromptReorderInteractionGeometry,
        gesture: PromptReorderGestureController,
        visual_mode: PromptReorderVisualModeOwner,
        landing_request: PromptReorderLandingRequestOwner,
        landing_preview: PromptReorderLandingPaintOwner,
        live_visuals: PromptReorderLiveVisualOwner,
        preview_visuals: PromptReorderPreviewVisualOwner,
        preview_paint_snapshots: PromptReorderPreviewPaintSnapshotOwner,
        animation: PromptReorderAnimationPresentationOwner,
        raster: PromptReorderRasterPublicationOwner,
        insertion_marker: PromptReorderInsertionMarkerOwner,
        metrics: PromptReorderInteractionMetricsOwner,
        diagnostics: PromptReorderInteractionDiagnosticsOwner,
        visual_style: PromptReorderVisualStyle,
        device_pixel_ratio: Callable[[], float],
        publish_surface: Callable[[PromptReorderSurfaceVisualPublication], None],
        publish_overlay: Callable[[PromptReorderViewRenderState], None],
    ) -> None:
        """Bind focused state owners and the two passive publication adapters."""

        self._geometry = geometry
        self._gesture = gesture
        self._visual_mode = visual_mode
        self._landing_request = landing_request
        self._landing_preview = landing_preview
        self._live_visuals = live_visuals
        self._preview_visuals = preview_visuals
        self._preview_paint_snapshots = preview_paint_snapshots
        self._animation = animation
        self._raster = raster
        self._insertion_marker = insertion_marker
        self._metrics = metrics
        self._diagnostics = diagnostics
        self._visual_style = visual_style
        self._device_pixel_ratio = device_pixel_ratio
        self._publish_surface = publish_surface
        self._publish_overlay = publish_overlay
        self._prepared = PromptReorderPreparedVisualOwner()

    @property
    def publication(self) -> PromptReorderPreparedVisualPublication:
        """Return the latest immutable render publication."""

        return self._prepared.publication

    @property
    def visual_style(self) -> PromptReorderVisualStyle:
        """Return the immutable style consumed by the current render owner."""

        return self._visual_style

    def set_visual_style(self, visual_style: PromptReorderVisualStyle) -> None:
        """Replace the theme-derived style consumed by the next frame."""

        self._visual_style = visual_style

    def sync(self, *, reason: str) -> None:
        """Prepare and publish one frame while reporting unsafe ownership."""

        publication = self._prepare()
        if publication.unsafe_transient_indices:
            self._metrics.record_anomaly()
            self._diagnostics.log_event(
                "paint_ownership.incomplete_transient",
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                reason=reason,
                segment_indices=publication.unsafe_transient_indices,
            )
        self._publish(publication)

    def clear(self) -> None:
        """Publish one empty frame to both passive paint adapters."""

        self._publish(self._prepared.clear())

    def _prepare(self) -> PromptReorderPreparedVisualPublication:
        """Prepare one frame from single reads of coherent owner publications."""

        geometry_state = self._geometry.state
        gesture_state = self._gesture.state
        preview_active = self._visual_mode.preview_active()
        preview_visuals = self._preview_visuals.visuals_by_index
        preview_indices = (
            tuple(
                segment_index
                for segment_index in geometry_state.ordered_segment_indices
                if segment_index in preview_visuals
            )
            if preview_active
            else ()
        )
        landing_request = self._landing_request_for_frame(
            preview_active=preview_active,
            dragged_segment_index=gesture_state.dragged_segment_index,
            has_active_target=gesture_state.active_drop_target is not None,
        )
        landing_preview = None
        if preview_active:
            if landing_request is None:
                raise RuntimeError("Preview rendering requires a landing request.")
            landing_result = self._landing_preview.landing_preview_paint_state(
                landing_request,
                visual_style=self._visual_style,
            )
            landing_preview = landing_result.paint_state
            self._geometry.set_active_placement(landing_result.active_placement)

        live_publication = self._live_visuals.publication
        live_chip_snapshot = live_publication.chip_geometry
        live_geometries = (
            _EMPTY_GEOMETRIES
            if live_chip_snapshot is None
            else live_chip_snapshot.geometries_by_chip_index
        )
        preview_chip_snapshot = geometry_state.preview_chip_geometry_snapshot
        preview_geometries = (
            _EMPTY_GEOMETRIES
            if preview_chip_snapshot is None
            else preview_chip_snapshot.geometries_by_chip_index
        )
        live_indices = geometry_state.initial_ordered_indices
        device_pixel_ratio = self._device_pixel_ratio()
        live_rasters: Mapping[int, ReorderRasterEntry] = _EMPTY_RASTERS
        preview_rasters: Mapping[int, ReorderRasterEntry] = _EMPTY_RASTERS
        if preview_active:
            preview_rasters = self._raster.entries_for(
                "preview",
                snapshots_by_index=self._preview_paint_snapshots.snapshots_by_index,
                styles_by_index=self._styles_by_index(
                    preview_indices,
                    dragged_segment_index=gesture_state.dragged_segment_index,
                    hovered_segment_index=gesture_state.hovered_segment_index,
                    active_segment_index=gesture_state.active_segment_index,
                ),
                device_pixel_ratio=device_pixel_ratio,
            )
        else:
            live_rasters = self._raster.entries_for(
                "live",
                snapshots_by_index=live_publication.visual_snapshots_by_index,
                styles_by_index=self._styles_by_index(
                    live_indices,
                    dragged_segment_index=gesture_state.dragged_segment_index,
                    hovered_segment_index=gesture_state.hovered_segment_index,
                    active_segment_index=gesture_state.active_segment_index,
                ),
                device_pixel_ratio=device_pixel_ratio,
            )
        return self._prepared.prepare(
            PromptReorderViewRenderInput(
                visual_style=self._visual_style,
                preview_active=preview_active,
                live_ordered_segment_indices=live_indices,
                preview_ordered_segment_indices=preview_indices,
                live_geometries_by_index=live_geometries,
                preview_geometries_by_index=preview_geometries,
                live_visuals_by_index=live_publication.visuals_by_index,
                preview_visuals_by_index=preview_visuals,
                dragged_segment_index=gesture_state.dragged_segment_index,
                hovered_segment_index=gesture_state.hovered_segment_index,
                active_segment_index=gesture_state.active_segment_index,
                live_visual_snapshots_by_index=(
                    live_publication.visual_snapshots_by_index
                ),
                preview_visual_snapshots_by_index=(
                    self._preview_paint_snapshots.snapshots_by_index
                ),
                live_raster_entries_by_index=live_rasters,
                preview_raster_entries_by_index=preview_rasters,
                marker_rect=self._insertion_marker.marker_rect(
                    landing_request=landing_request
                ),
                landing_preview=landing_preview,
                gesture_id=self._metrics.gesture_id,
                event_id=self._metrics.event_id,
                paint_rect_overrides_by_index=(
                    self._animation.publication.paint_rects_by_index
                ),
            )
        )

    def _landing_request_for_frame(
        self,
        *,
        preview_active: bool,
        dragged_segment_index: int | None,
        has_active_target: bool,
    ) -> PromptReorderLandingShadowRequest | None:
        """Build at most one landing request when frame policy can consume it."""

        if not preview_active and (
            dragged_segment_index is None or not has_active_target
        ):
            return None
        return self._landing_request.build()

    def _styles_by_index(
        self,
        segment_indices: tuple[int, ...],
        *,
        dragged_segment_index: int | None,
        hovered_segment_index: int | None,
        active_segment_index: int | None,
    ) -> dict[int, PromptChipPaintStyle]:
        """Return exact per-segment styles for one active raster lane."""

        return {
            segment_index: self._visual_style.paint_style_for_segment(
                segment_index,
                dragged_segment_index=dragged_segment_index,
                hovered_segment_index=hovered_segment_index,
                active_segment_index=active_segment_index,
            )
            for segment_index in segment_indices
        }

    def _publish(
        self,
        publication: PromptReorderPreparedVisualPublication,
    ) -> None:
        """Apply one prepared publication to both passive paint adapters."""

        self._publish_surface(publication.surface)
        self._publish_overlay(publication.overlay_state)
