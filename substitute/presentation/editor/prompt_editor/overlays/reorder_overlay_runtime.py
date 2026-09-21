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

"""Describe the composed runtime consumed by the reorder overlay surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtWidgets import QWidget

from ..interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from ..projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from .reorder_animation_presentation import PromptReorderAnimationPresentationOwner
from .reorder_autoscroll import PromptReorderAutoscrollOwner
from .reorder_drag_proxy_visual_owner import PromptReorderDragProxyVisualOwner
from .reorder_gesture_controller import PromptReorderGestureController
from .reorder_interaction_intents import PromptReorderInteractionIntentOwner
from .reorder_keyboard_interaction import PromptReorderKeyboardInteractionOwner
from .reorder_landing_request_owner import PromptReorderLandingRequestOwner
from .reorder_landing_resolution import PromptReorderLandingResolutionOwner
from .reorder_live_visual_owner import PromptReorderLiveVisualOwner
from .reorder_overlay_ports import PromptReorderEditor
from .reorder_overlay_session_activation import (
    PromptReorderOverlaySessionActivationOwner,
)
from .reorder_overlay_visual_lifecycle import (
    PromptReorderOverlayVisualLifecycleOwner,
)
from .reorder_performance_counters import PromptReorderPerformanceCountersOwner
from .reorder_pointer_drag_completion_owner import (
    PromptReorderPointerDragCompletionOwner,
)
from .reorder_pointer_drag_start_owner import PromptReorderPointerDragStartOwner
from .reorder_pointer_move_owner import PromptReorderPointerMoveOwner
from .reorder_pointer_region_visual_owner import (
    PromptReorderPointerRegionVisualOwner,
)
from .reorder_pointer_regions import (
    PromptReorderPointerGestureController,
    PromptReorderPointerInput,
    PromptReorderPointerRegions,
    PromptReorderPointerSurface,
)
from .reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from .reorder_preview_build_facts import PromptReorderPreviewBuildFactsOwner
from .reorder_preview_frame_transition import PromptReorderPreviewFrameTransitionOwner
from .reorder_preview_sync_context import PromptReorderPreviewSyncContextOwner
from .reorder_preview_visual_owner import PromptReorderPreviewVisualOwner
from .reorder_raster_publication import PromptReorderRasterPublicationOwner
from .reorder_render_publication_owner import PromptReorderRenderPublicationOwner
from .reorder_telemetry import PromptReorderTelemetry
from .reorder_view import PromptReorderView
from .reorder_viewport_frame_refresh import PromptReorderViewportFrameRefreshOwner
from .reorder_viewport_geometry import PromptReorderViewportGeometryOwner
from .reorder_visual_lifetime import PromptReorderVisualLifetime
from .reorder_visual_mode import PromptReorderVisualModeOwner
from .reorder_visual_session import PromptReorderVisualSessionOwner


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayRuntimeMount:
    """Provide the Qt surface and callbacks needed to compose one runtime."""

    surface: QWidget
    editor: PromptReorderEditor
    view: PromptReorderView
    geometry: PromptReorderInteractionGeometry
    preview_visuals: PromptReorderPreviewVisualOwner
    interaction_metrics: PromptReorderInteractionMetricsOwner
    gesture: PromptReorderGestureController
    pointer_gesture_controller: PromptReorderPointerGestureController
    pointer_surface: PromptReorderPointerSurface
    emit_preview_layout_changed: Callable[[], None]
    handle_animation_frame: Callable[[], None]
    publish_warmed_rasters: Callable[[], None]
    refresh_geometry: Callable[[str], None]


@dataclass(frozen=True, slots=True)
class PromptReorderOverlayRuntime:
    """Hold the authoritative collaborators behind one mounted overlay surface."""

    geometry: PromptReorderInteractionGeometry
    viewport_geometry: PromptReorderViewportGeometryOwner
    preview_visuals: PromptReorderPreviewVisualOwner
    preview_paint_snapshots: PromptReorderPreviewPaintSnapshotOwner
    interaction_metrics: PromptReorderInteractionMetricsOwner
    telemetry: PromptReorderTelemetry
    live_visuals: PromptReorderLiveVisualOwner
    interaction_intents: PromptReorderInteractionIntentOwner
    landing_request: PromptReorderLandingRequestOwner
    landing_resolution: PromptReorderLandingResolutionOwner
    animation: PromptReorderAnimationPresentationOwner
    raster: PromptReorderRasterPublicationOwner
    visual_session: PromptReorderVisualSessionOwner
    pointer_regions: PromptReorderPointerRegions
    pointer_input: PromptReorderPointerInput
    gesture: PromptReorderGestureController
    visual_mode: PromptReorderVisualModeOwner
    render: PromptReorderRenderPublicationOwner
    keyboard: PromptReorderKeyboardInteractionOwner
    drag_proxy: PromptReorderDragProxyVisualOwner
    pointer_region_visuals: PromptReorderPointerRegionVisualOwner
    preview_frame: PromptReorderPreviewFrameTransitionOwner
    viewport_refresh: PromptReorderViewportFrameRefreshOwner
    autoscroll: PromptReorderAutoscrollOwner
    pointer_move: PromptReorderPointerMoveOwner
    pointer_drag_start: PromptReorderPointerDragStartOwner
    pointer_drag_completion: PromptReorderPointerDragCompletionOwner
    performance: PromptReorderPerformanceCountersOwner
    visual_lifecycle: PromptReorderOverlayVisualLifecycleOwner
    session_activation: PromptReorderOverlaySessionActivationOwner
    preview_sync_context: PromptReorderPreviewSyncContextOwner
    preview_build_facts: PromptReorderPreviewBuildFactsOwner
    visual_lifetime: PromptReorderVisualLifetime


class PromptReorderOverlayRuntimeFactory(Protocol):
    """Compose one complete reorder runtime for a mounted Qt surface."""

    def __call__(
        self,
        mount: PromptReorderOverlayRuntimeMount,
    ) -> PromptReorderOverlayRuntime:
        """Return the runtime wired to the supplied surface."""


__all__ = [
    "PromptReorderOverlayRuntime",
    "PromptReorderOverlayRuntimeFactory",
    "PromptReorderOverlayRuntimeMount",
]
