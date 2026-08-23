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

"""Verify atomic reorder render preparation and publication ownership."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from PySide6.QtGui import QColor

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_animation_presentation import (
    PromptReorderAnimationPresentationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_insertion_marker_owner import (
    PromptReorderInsertionMarkerOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderLandingShadowRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_paint_cache import (
    PromptReorderLandingShadowPaintResult,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_request_owner import (
    PromptReorderLandingRequestOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_paint import (
    PromptReorderLandingPaintOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_live_visual_owner import (
    PromptReorderLiveVisualOwner,
    PromptReorderLiveVisualPublication,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_raster_publication import (
    PromptReorderRasterPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_publication_owner import (
    PromptReorderRenderPublicationOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_render_state import (
    PromptReorderViewRenderState,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_mode import (
    PromptReorderVisualModeOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_visual_style import (
    PromptReorderVisualStyle,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_surface_visual_state import (
    PromptReorderSurfaceVisualPublication,
)


class _Geometry:
    """Publish stable empty geometry and capture active-placement writes."""

    def __init__(self) -> None:
        """Initialize one two-segment geometry publication."""

        self.state = PromptReorderInteractionGeometryState(
            initial_ordered_indices=(0, 1),
            ordered_segment_indices=(1, 0),
        )
        self.placements: list[object | None] = []

    def set_active_placement(self, placement: object | None) -> None:
        """Capture one landing-derived placement."""

        self.placements.append(placement)


class _VisualMode:
    """Return one configured paint mode."""

    def __init__(self, *, preview_active: bool) -> None:
        """Store the configured mode."""

        self._preview_active = preview_active

    def preview_active(self) -> bool:
        """Return the configured mode."""

        return self._preview_active


class _LandingRequest:
    """Count coherent landing-request construction."""

    def __init__(self) -> None:
        """Initialize request counting."""

        self.build_count = 0
        self.request = cast(PromptReorderLandingShadowRequest, object())

    def build(self) -> PromptReorderLandingShadowRequest:
        """Return one stable opaque request."""

        self.build_count += 1
        return self.request


class _LandingVisual:
    """Return an empty landing result and count render requests."""

    def __init__(self) -> None:
        """Initialize request counting."""

        self.paint_count = 0

    def landing_preview_paint_state(
        self,
        _request: PromptReorderLandingShadowRequest,
        *,
        visual_style: PromptReorderVisualStyle,
    ) -> PromptReorderLandingShadowPaintResult:
        """Return one empty but complete landing publication."""

        _ = visual_style
        self.paint_count += 1
        return PromptReorderLandingShadowPaintResult(
            paint_state=None,
            active_placement=None,
        )


class _LiveVisuals:
    """Publish one empty coherent live-visual generation."""

    publication = PromptReorderLiveVisualPublication(
        revision=1,
        geometry_key=None,
        chip_geometry=None,
        visuals_by_index={},
        visual_snapshots_by_index={},
        owned_ranges_by_index={},
    )


class _PreviewVisuals:
    """Publish a configured preview visual mapping."""

    def __init__(self, indices: tuple[int, ...]) -> None:
        """Create opaque visuals for supplied semantic indices."""

        self.visuals_by_index = {
            segment_index: cast(object, SimpleNamespace()) for segment_index in indices
        }


class _PreviewPaintSnapshots:
    """Publish empty preview projection snapshots."""

    snapshots_by_index: dict[object, object] = {}


class _Animation:
    """Publish an empty animation paint override mapping."""

    publication = SimpleNamespace(paint_rects_by_index={})


class _Raster:
    """Capture the single active raster lane prepared per frame."""

    def __init__(self) -> None:
        """Initialize lane recording."""

        self.lanes: list[str] = []

    def entries_for(self, lane: str, **_facts: object) -> dict[object, object]:
        """Record one lane request and return no prepared pixmaps."""

        self.lanes.append(lane)
        return {}


class _InsertionMarker:
    """Capture the frame's already-built landing request."""

    def __init__(self) -> None:
        """Initialize request capture."""

        self.requests: list[PromptReorderLandingShadowRequest | None] = []

    def marker_rect(
        self,
        *,
        landing_request: PromptReorderLandingShadowRequest | None,
    ) -> None:
        """Capture the request and return no marker."""

        self.requests.append(landing_request)


class _Diagnostics:
    """Capture render ownership diagnostics."""

    def __init__(self) -> None:
        """Initialize event capture."""

        self.events: list[str] = []

    def log_event(self, event: str, **_context: object) -> None:
        """Record one event."""

        self.events.append(event)


class _DevicePixelRatio:
    """Count bounded view-scale queries."""

    def __init__(self) -> None:
        """Initialize query counting."""

        self.call_count = 0

    def __call__(self) -> float:
        """Return one stable device scale."""

        self.call_count += 1
        return 1.0


def test_live_render_stops_before_landing_work_and_publishes_atomically() -> None:
    """Live rendering must avoid landing work and publish only the live lane."""

    owner, facts = _owner(preview_active=False, preview_indices=())

    owner.sync(reason="owner_test")

    assert facts.landing_request.build_count == 0
    assert facts.landing_visual.paint_count == 0
    assert facts.insertion_marker.requests == [None]
    assert facts.raster.lanes == ["live"]
    assert facts.device_pixel_ratio.call_count == 1
    assert facts.surface_publications[-1] is owner.publication.surface
    assert facts.overlay_publications[-1] is owner.publication.overlay_state
    assert owner.publication.overlay_state.preview_active is False


def test_preview_render_builds_one_landing_request_and_clear_republishes() -> None:
    """Preview rendering must share one request and clear both paint adapters."""

    owner, facts = _owner(preview_active=True, preview_indices=(0, 1))

    owner.sync(reason="owner_test")
    rendered_revision = owner.publication.revision

    assert facts.landing_request.build_count == 1
    assert facts.landing_visual.paint_count == 1
    assert facts.insertion_marker.requests == [facts.landing_request.request]
    assert facts.raster.lanes == ["preview"]
    assert facts.geometry.placements == [None]
    assert owner.publication.overlay_state.preview_active is True

    owner.clear()

    assert owner.publication.revision == rendered_revision + 1
    assert facts.surface_publications[-1] is owner.publication.surface
    assert facts.overlay_publications[-1] is owner.publication.overlay_state
    assert facts.overlay_publications[-1] == PromptReorderViewRenderState()


class _OwnerFacts:
    """Collect observable collaborators returned with one owner."""

    def __init__(self) -> None:
        """Initialize mutable test facts."""

        self.geometry = _Geometry()
        self.landing_request = _LandingRequest()
        self.landing_visual = _LandingVisual()
        self.raster = _Raster()
        self.insertion_marker = _InsertionMarker()
        self.device_pixel_ratio = _DevicePixelRatio()
        self.surface_publications: list[PromptReorderSurfaceVisualPublication] = []
        self.overlay_publications: list[PromptReorderViewRenderState] = []


def _owner(
    *,
    preview_active: bool,
    preview_indices: tuple[int, ...],
) -> tuple[PromptReorderRenderPublicationOwner, _OwnerFacts]:
    """Return one render owner and its observable focused collaborators."""

    facts = _OwnerFacts()
    metrics = PromptReorderInteractionMetricsOwner()
    diagnostics = _Diagnostics()
    owner = PromptReorderRenderPublicationOwner(
        geometry=cast(PromptReorderInteractionGeometry, facts.geometry),
        gesture=PromptReorderGestureController(),
        visual_mode=cast(
            PromptReorderVisualModeOwner,
            _VisualMode(preview_active=preview_active),
        ),
        landing_request=cast(
            PromptReorderLandingRequestOwner,
            facts.landing_request,
        ),
        landing_preview=cast(PromptReorderLandingPaintOwner, facts.landing_visual),
        live_visuals=cast(PromptReorderLiveVisualOwner, _LiveVisuals()),
        preview_visuals=cast(
            PromptReorderPreviewVisualOwner,
            _PreviewVisuals(preview_indices),
        ),
        preview_paint_snapshots=cast(
            PromptReorderPreviewPaintSnapshotOwner,
            _PreviewPaintSnapshots(),
        ),
        animation=cast(PromptReorderAnimationPresentationOwner, _Animation()),
        raster=cast(PromptReorderRasterPublicationOwner, facts.raster),
        insertion_marker=cast(
            PromptReorderInsertionMarkerOwner,
            facts.insertion_marker,
        ),
        metrics=metrics,
        diagnostics=cast(PromptReorderInteractionDiagnosticsOwner, diagnostics),
        visual_style=_style(),
        device_pixel_ratio=facts.device_pixel_ratio,
        publish_surface=facts.surface_publications.append,
        publish_overlay=facts.overlay_publications.append,
    )
    return owner, facts


def _style() -> PromptReorderVisualStyle:
    """Return one deterministic visual style."""

    return PromptReorderVisualStyle(
        rest_fill=QColor("#202020"),
        rest_border=QColor("#303030"),
        hover_fill=QColor("#404040"),
        hover_border=QColor("#505050"),
        active_fill=QColor("#606060"),
        active_border=QColor("#707070"),
        drag_fill=QColor("#808080"),
        drag_border=QColor("#909090"),
        marker_color=QColor("#ff00ff"),
    )
