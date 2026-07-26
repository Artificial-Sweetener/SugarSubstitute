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

"""Own drag-scoped held-shadow capture and landing-session lifecycle."""

from __future__ import annotations

from dataclasses import dataclass

from .reorder_landing_capture import prompt_reorder_held_shadow_capture
from .reorder_landing_diagnostics import PromptReorderLandingDiagnostics
from .reorder_landing_events import PromptReorderLandingEventPublisher
from .reorder_landing_models import PromptReorderHeldShadowCaptureInput
from .reorder_landing_state import (
    PromptReorderLandingState,
    PromptReorderLandingStateOwner,
)


@dataclass(slots=True)
class PromptReorderLandingSessionOwner:
    """Apply drag-lifecycle transitions to the authoritative landing state."""

    state: PromptReorderLandingStateOwner
    diagnostics: PromptReorderLandingDiagnostics
    events: PromptReorderLandingEventPublisher

    @property
    def publication(self) -> PromptReorderLandingState:
        """Return the current immutable drag-scoped landing state."""

        return self.state.publication

    def reset_session_state(self) -> None:
        """Clear retained landing state for a replacement overlay session."""

        self.reset_drag_state()

    def reset_drag_state(self) -> None:
        """Clear retained shadow state and per-drag diagnostic counters."""

        self.state.reset()
        self.diagnostics.reset()

    def clear_preview_state(self) -> None:
        """Clear retained preview details while preserving the held shadow."""

        self.state.clear_preview()

    def clear_held_shadow(self) -> None:
        """Discard held chrome when its source geometry is no longer valid."""

        self.state.clear_held_shadow()

    def capture_held_shadow(
        self,
        capture: PromptReorderHeldShadowCaptureInput,
    ) -> None:
        """Capture the first visible-chip chrome metrics for this drag."""

        if self.state.publication.held_shadow_geometry is not None:
            return
        outcome = prompt_reorder_held_shadow_capture(capture)
        geometry = outcome.geometry
        if geometry is None:
            self.state.record_missing_held_shadow()
            self.events.held_shadow_missing(capture, outcome)
            return
        self.state.adopt_held_shadow(geometry)
        context = self.events.held_shadow_captured(capture, geometry)
        if geometry.low_confidence:
            self.diagnostics.expected(
                None,
                "diagnostic.low_confidence_shadow_metrics",
                dragged_segment_index=capture.chip_index,
                **context,
            )


__all__ = ["PromptReorderLandingSessionOwner"]
