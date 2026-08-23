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

"""Verify complete prompt-reorder preview-geometry refresh transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_gesture_controller import (
    PromptReorderGestureController,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_interaction_diagnostics import (
    PromptReorderInteractionDiagnosticsOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_models import (
    PromptReorderLandingShadowRequest,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_request_owner import (
    PromptReorderLandingRequestOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_resolution import (
    PromptReorderLandingResolutionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_geometry_refresh_owner import (
    PromptReorderPreviewGeometryRefreshOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_paint_snapshot_owner import (
    PromptReorderPreviewPaintSnapshotOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_preview_visual_owner import (
    PromptReorderPreviewVisualOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_viewport_geometry import (
    PromptReorderViewportGeometryOwner,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_state import (
    reorder_overlay_position_geometry_key,
)


@dataclass(frozen=True, slots=True)
class _Refresh:
    """Provide the refresh facts consumed by the transition owner."""

    base_drag_geometry_reused: bool = False
    base_drag_chip_snapshot: object | None = None
    drop_target_visuals: tuple[object, ...] = ()
    drop_target_lanes: tuple[object, ...] = ()


@dataclass(frozen=True, slots=True)
class _Publication:
    """Provide one prepared publication."""

    geometry: _Refresh
    visuals_by_index: dict[int, object]


@dataclass(frozen=True, slots=True)
class _Outcome:
    """Provide one preview-owner result."""

    publication: _Publication
    rebuilt: bool
    reused_chip_count: int = 0
    rebuilt_chip_count: int = 0
    reuse_rejected_count: int = 0


class _Geometry:
    """Publish immutable state and capture placement updates."""

    def __init__(self) -> None:
        """Initialize an empty geometry publication."""

        self.state = PromptReorderInteractionGeometryState()
        self.placements: list[object | None] = []

    def set_active_placement(self, placement: object | None) -> None:
        """Capture one placement update."""

        self.placements.append(placement)


class _PreviewVisuals:
    """Return one configured preview preparation outcome."""

    def __init__(self, outcome: _Outcome) -> None:
        """Store the configured result."""

        self.outcome = outcome
        self.prepare_count = 0

    def prepare(self, **_facts: object) -> _Outcome:
        """Return the configured result and count the bounded request."""

        self.prepare_count += 1
        return self.outcome


class _Viewport:
    """Return one bounded viewport identity."""

    def __init__(self) -> None:
        """Initialize request counting."""

        self.call_count = 0

    def position_geometry_key(self) -> object:
        """Return one stable key."""

        self.call_count += 1
        return reorder_overlay_position_geometry_key(
            viewport_left=0,
            viewport_top=0,
            viewport_width=300,
            viewport_height=180,
            content_left=4,
            content_top=4,
            content_width=280,
            content_height=160,
            scroll_offset=0,
        )


class _PaintSnapshots:
    """Count preview paint-snapshot invalidations."""

    def __init__(self) -> None:
        """Initialize the counter."""

        self.clear_count = 0

    def clear(self) -> None:
        """Record one invalidation."""

        self.clear_count += 1


class _LandingRequest:
    """Count coherent landing-request builds."""

    def __init__(self) -> None:
        """Initialize the counter."""

        self.build_count = 0

    def build(self) -> PromptReorderLandingShadowRequest:
        """Return an opaque request accepted by the landing fake."""

        self.build_count += 1
        return cast(PromptReorderLandingShadowRequest, object())


class _LandingVisual:
    """Capture landing transition calls."""

    def __init__(self) -> None:
        """Initialize call counters."""

        self.attach_count = 0
        self.ready_count = 0

    def attach_expected_landing_to_active_placement(
        self,
        _request: PromptReorderLandingShadowRequest,
    ) -> None:
        """Record placement attachment."""

        self.attach_count += 1

    def mark_initial_landing_shadow_ready(
        self,
        _request: PromptReorderLandingShadowRequest,
    ) -> None:
        """Record initial-shadow publication."""

        self.ready_count += 1


class _Diagnostics:
    """Capture timing and event publication."""

    def __init__(self, elapsed_ms: float = 1.0) -> None:
        """Store deterministic elapsed time."""

        self.elapsed_ms = elapsed_ms
        self.events: list[str] = []

    def log_timing(self, event: str, **_context: object) -> float:
        """Record timing publication."""

        self.events.append(event)
        return self.elapsed_ms

    def log_event(self, event: str, **_context: object) -> None:
        """Record one structured event."""

        self.events.append(event)


def test_preview_geometry_refresh_suppresses_all_unchanged_followup_work() -> None:
    """An unchanged preview must stop before paint, landing, and diagnostics."""

    outcome = _Outcome(
        publication=_Publication(geometry=_Refresh(), visuals_by_index={}),
        rebuilt=False,
    )
    owner, metrics, viewport, paint, landing_request, landing, diagnostics = _owner(
        outcome
    )

    assert owner.refresh() is False
    assert metrics.snapshot().preview_geometry_suppressed_count == 1
    assert viewport.call_count == 1
    assert paint.clear_count == 0
    assert landing_request.build_count == 0
    assert landing.attach_count == 0
    assert diagnostics.events == []


def test_preview_geometry_refresh_publishes_one_complete_changed_transition() -> None:
    """A changed preview must update metrics, paint, landing, and diagnostics."""

    outcome = _Outcome(
        publication=_Publication(
            geometry=_Refresh(),
            visuals_by_index={1: object()},
        ),
        rebuilt=True,
        reused_chip_count=2,
        rebuilt_chip_count=1,
        reuse_rejected_count=3,
    )
    owner, metrics, viewport, paint, landing_request, landing, diagnostics = _owner(
        outcome, elapsed_ms=9.0
    )

    assert owner.refresh() is True
    snapshot = metrics.snapshot()
    assert snapshot.preview_geometry_full_count == 1
    assert snapshot.preview_geometry_reused_chip_count == 2
    assert snapshot.preview_geometry_rebuilt_chip_count == 1
    assert snapshot.preview_geometry_reuse_rejected_count == 3
    assert viewport.call_count == 1
    assert paint.clear_count == 1
    assert landing_request.build_count == 2
    assert landing.attach_count == 1
    assert landing.ready_count == 1
    assert diagnostics.events == [
        "preview_geometry.total",
        "preview_geometry.full_geometry_applied",
        "budget.preview_geometry_exceeded",
    ]


def _owner(
    outcome: _Outcome,
    *,
    elapsed_ms: float = 1.0,
) -> tuple[
    PromptReorderPreviewGeometryRefreshOwner,
    PromptReorderInteractionMetricsOwner,
    _Viewport,
    _PaintSnapshots,
    _LandingRequest,
    _LandingVisual,
    _Diagnostics,
]:
    """Return one owner and its observable collaborators."""

    geometry = _Geometry()
    preview = _PreviewVisuals(outcome)
    viewport = _Viewport()
    paint = _PaintSnapshots()
    landing_request = _LandingRequest()
    landing = _LandingVisual()
    diagnostics = _Diagnostics(elapsed_ms)
    metrics = PromptReorderInteractionMetricsOwner()
    owner = PromptReorderPreviewGeometryRefreshOwner(
        geometry=cast(PromptReorderInteractionGeometry, geometry),
        gesture=PromptReorderGestureController(),
        viewport=cast(PromptReorderViewportGeometryOwner, viewport),
        preview_visuals=cast(PromptReorderPreviewVisualOwner, preview),
        preview_paint_snapshots=cast(
            PromptReorderPreviewPaintSnapshotOwner,
            paint,
        ),
        landing_request=cast(PromptReorderLandingRequestOwner, landing_request),
        landing_preview=cast(PromptReorderLandingResolutionOwner, landing),
        metrics=metrics,
        diagnostics=cast(PromptReorderInteractionDiagnosticsOwner, diagnostics),
    )
    return owner, metrics, viewport, paint, landing_request, landing, diagnostics
