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

"""Cover reorder insertion-marker preparation."""

from __future__ import annotations

from typing import cast

from substitute.presentation.editor.prompt_editor.interactions.reorder_interaction_metrics import (
    PromptReorderInteractionMetricsOwner,
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
from substitute.presentation.editor.prompt_editor.overlays.reorder_landing_resolution import (
    PromptReorderLandingResolutionOwner,
)
from substitute.presentation.editor.prompt_editor.overlays.reorder_telemetry import (
    PromptReorderTelemetry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry import (
    PromptReorderInteractionGeometry,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_interaction_geometry_state import (
    PromptReorderInteractionGeometryState,
)


class _Geometry:
    """Publish empty immutable target geometry."""

    state = PromptReorderInteractionGeometryState()


class _Diagnostics:
    """Capture marker diagnostics."""

    def __init__(self) -> None:
        """Initialize empty events."""

        self.events: list[str] = []

    def log_event(self, event: str, **_context: object) -> None:
        """Record one expected event."""

        self.events.append(event)

    def log_anomaly(self, event: str, **_context: object) -> None:
        """Record one anomaly."""

        self.events.append(event)


def test_insertion_marker_stops_before_landing_work_without_active_gesture() -> None:
    """Inactive gesture state must return no marker from bounded state reads."""

    diagnostics = _Diagnostics()
    owner = PromptReorderInsertionMarkerOwner(
        geometry=cast(PromptReorderInteractionGeometry, _Geometry()),
        gesture=PromptReorderGestureController(),
        landing_preview=cast(PromptReorderLandingResolutionOwner, object()),
        metrics=PromptReorderInteractionMetricsOwner(),
        diagnostics=cast(PromptReorderInteractionDiagnosticsOwner, diagnostics),
        telemetry=PromptReorderTelemetry(),
    )

    assert owner.marker_rect(landing_request=None) is None
    assert diagnostics.events == ["target_visual.marker_skipped"]
