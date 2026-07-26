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

"""Own immutable reorder landing interaction state and operational counters."""

from __future__ import annotations

from dataclasses import dataclass, replace

from substitute.application.prompt_editor.reorder.views import PromptReorderDropTarget

from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from .chip_visuals import PromptChipVisual
from .reorder_landing_models import PromptReorderHeldShadowGeometry


@dataclass(frozen=True, slots=True)
class PromptReorderLandingOperationalCounters:
    """Expose retained-state transitions without cache or diagnostic metrics."""

    initial_shadow_sync_count: int = 0
    initial_shadow_ready_count: int = 0
    stale_shadow_rejected_count: int = 0
    held_shadow_capture_count: int = 0
    held_shadow_missing_count: int = 0
    pending_shadow_fallback_count: int = 0
    pending_shadow_replaced_marker_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderLandingState:
    """Publish one coherent immutable landing interaction state."""

    revision: int = 0
    held_shadow_geometry: PromptReorderHeldShadowGeometry | None = None
    last_preview_visual: PromptChipVisual | None = None
    last_preview_target: PromptReorderDropTarget | None = None
    last_preview_event_id: int | None = None
    last_preview_geometry: PromptReorderChipGeometry | None = None
    last_preview_skip_reason: str = "none"
    last_rejected_target: PromptReorderDropTarget | None = None
    initial_shadow_sync_used: bool = False
    initial_shadow_ready: bool = False


@dataclass(slots=True)
class PromptReorderLandingStateOwner:
    """Apply landing state transitions and publish one immutable snapshot."""

    _publication: PromptReorderLandingState = PromptReorderLandingState()
    _counters: PromptReorderLandingOperationalCounters = (
        PromptReorderLandingOperationalCounters()
    )

    @property
    def publication(self) -> PromptReorderLandingState:
        """Return the current immutable landing state."""

        return self._publication

    @property
    def counters(self) -> PromptReorderLandingOperationalCounters:
        """Return immutable operational transition counters."""

        return self._counters

    def reset(self) -> None:
        """Clear all per-drag state and counters in one publication."""

        self._publication = PromptReorderLandingState(
            revision=self._publication.revision + 1
        )
        self._counters = PromptReorderLandingOperationalCounters()

    def clear_preview(self) -> None:
        """Clear retained preview details while preserving held geometry."""

        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            last_preview_visual=None,
            last_preview_target=None,
            last_preview_event_id=None,
            last_preview_geometry=None,
            last_preview_skip_reason="none",
            last_rejected_target=None,
        )

    def clear_held_shadow(self) -> None:
        """Clear held geometry and the skip reason derived from it."""

        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            held_shadow_geometry=None,
            last_preview_skip_reason="none",
        )

    def adopt_held_shadow(self, geometry: PromptReorderHeldShadowGeometry) -> bool:
        """Publish first held geometry and report whether adoption occurred."""

        if self._publication.held_shadow_geometry is not None:
            return False
        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            held_shadow_geometry=geometry,
        )
        self._increment("held_shadow_capture_count")
        return True

    def record_missing_held_shadow(self) -> None:
        """Count one drag-start capture without usable geometry."""

        self._increment("held_shadow_missing_count")

    def consume_initial_shadow_sync(self) -> bool:
        """Consume the one immediate initial-shadow synchronization allowance."""

        if self._publication.initial_shadow_sync_used:
            return False
        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            initial_shadow_sync_used=True,
        )
        self._increment("initial_shadow_sync_count")
        return True

    def mark_initial_shadow_ready(self) -> bool:
        """Publish first valid landing readiness and report whether it changed."""

        if self._publication.initial_shadow_ready:
            return False
        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            initial_shadow_ready=True,
        )
        self._increment("initial_shadow_ready_count")
        return True

    def record_rejected_target(
        self,
        target: PromptReorderDropTarget | None,
    ) -> None:
        """Publish one stale target rejection and increment its counter."""

        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            last_rejected_target=target,
        )
        self._increment("stale_shadow_rejected_count")

    def set_skip_reason(self, reason: str) -> None:
        """Publish a changed preview skip reason without duplicate allocation."""

        if self._publication.last_preview_skip_reason == reason:
            return
        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            last_preview_skip_reason=reason,
        )

    def publish_preview(
        self,
        *,
        visual: PromptChipVisual,
        geometry: PromptReorderChipGeometry,
        target: PromptReorderDropTarget | None,
        event_id: int | None,
    ) -> None:
        """Publish the prepared landing preview consumed by geometry adapters."""

        state = self._publication
        self._publication = replace(
            state,
            revision=state.revision + 1,
            last_preview_visual=visual,
            last_preview_geometry=geometry,
            last_preview_target=target,
            last_preview_event_id=event_id,
        )

    def record_pending_fallback(self) -> None:
        """Count one pending shadow that replaces the lightweight marker."""

        self._increment("pending_shadow_fallback_count")
        self._increment("pending_shadow_replaced_marker_count")

    def _increment(self, field_name: str) -> None:
        """Increment one immutable operational counter by name."""

        self._counters = replace(
            self._counters,
            **{field_name: getattr(self._counters, field_name) + 1},
        )


__all__ = [
    "PromptReorderLandingOperationalCounters",
    "PromptReorderLandingState",
    "PromptReorderLandingStateOwner",
]
