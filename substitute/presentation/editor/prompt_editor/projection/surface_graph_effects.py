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

"""Own effects that cross the prompt projection surface composition cycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF

from ..core.projection.document import PromptProjectionDisplayMode

if TYPE_CHECKING:
    from .autocomplete_preview_projection_owner import (
        PromptAutocompletePreviewProjectionOwner,
    )
    from .freshness_controller import PromptProjectionFreshnessController
    from .surface_lifecycle_runtime import PromptProjectionSurfaceLifecycleRuntime
    from .surface_presentation_runtime import PromptProjectionSurfacePresentationRuntime


@dataclass(frozen=True, slots=True)
class PromptProjectionSurfaceGraphEffectBindings:
    """Declare effects implemented only after the surface graph is complete."""

    projection_is_stale: Callable[[], bool]
    rebuild_projection: Callable[[], None]
    reconcile_autocomplete: Callable[[int, bool], None]
    refresh_active_projection: Callable[[], None]
    ensure_caret_visible: Callable[[], None]
    refresh_caret_layers: Callable[[], None]
    refresh_deferred_caret_layers: Callable[[], None]
    restart_caret_blink: Callable[[], None]
    update_caret_paint: Callable[[QRectF | None], None]
    diagnostic_layer_changed: Callable[[], None]
    rebuild_active_projection: Callable[[], None]
    prepare_focus_chrome: Callable[[], None]
    schedule_caret_blink: Callable[[bool], None]
    is_projected: Callable[[], bool]
    apply_session_paint_state: Callable[[], bool]


class PromptProjectionSurfaceGraphEffects:
    """Reject graph-dependent effects until all authoritative owners are bound."""

    def __init__(self) -> None:
        """Create an explicitly unwired surface-graph effect port."""

        self._bindings: PromptProjectionSurfaceGraphEffectBindings | None = None

    def bind(self, bindings: PromptProjectionSurfaceGraphEffectBindings) -> None:
        """Bind every graph effect once after composition completes."""

        if self._bindings is not None:
            raise RuntimeError("Prompt projection surface graph effects are wired.")
        self._bindings = bindings

    def projection_is_stale(self) -> bool:
        """Return whether committed projection geometry is stale but safe."""

        return self._require_bindings().projection_is_stale()

    def rebuild_projection(self) -> None:
        """Rebuild the committed projection."""

        self._require_bindings().rebuild_projection()

    def reconcile_autocomplete(
        self,
        cursor_position: int,
        selection_is_empty: bool,
    ) -> None:
        """Reconcile autocomplete after one caret transition."""

        self._require_bindings().reconcile_autocomplete(
            cursor_position,
            selection_is_empty,
        )

    def refresh_active_projection(self) -> None:
        """Refresh the active span against current caret state."""

        self._require_bindings().refresh_active_projection()

    def ensure_caret_visible(self) -> None:
        """Ensure the current caret is visible."""

        self._require_bindings().ensure_caret_visible()

    def refresh_caret_layers(self) -> None:
        """Publish immediate caret render layers."""

        self._require_bindings().refresh_caret_layers()

    def refresh_deferred_caret_layers(self) -> None:
        """Publish deferred caret render layers."""

        self._require_bindings().refresh_deferred_caret_layers()

    def restart_caret_blink(self) -> None:
        """Restart the caret blink cycle."""

        self._require_bindings().restart_caret_blink()

    def update_caret_paint(self, previous_caret_rect: QRectF | None) -> None:
        """Invalidate current and previous caret paint bounds."""

        self._require_bindings().update_caret_paint(previous_caret_rect)

    def diagnostic_layer_changed(self) -> None:
        """Publish a changed diagnostic render layer."""

        self._require_bindings().diagnostic_layer_changed()

    def rebuild_active_projection(self) -> None:
        """Rebuild transient active-projection state."""

        self._require_bindings().rebuild_active_projection()

    def prepare_focus_chrome(self) -> None:
        """Prepare source chrome after a focus transition."""

        self._require_bindings().prepare_focus_chrome()

    def schedule_caret_blink(self, reset_cycle: bool) -> None:
        """Schedule caret blink reconciliation after focus settles."""

        self._require_bindings().schedule_caret_blink(reset_cycle)

    def is_projected(self) -> bool:
        """Return whether the surface currently displays projected content."""

        return self._require_bindings().is_projected()

    def apply_session_paint_state(self) -> bool:
        """Apply session paint state to the current active projection."""

        return self._require_bindings().apply_session_paint_state()

    def _require_bindings(self) -> PromptProjectionSurfaceGraphEffectBindings:
        """Return bound effects or reject construction-time dispatch."""

        if self._bindings is None:
            raise RuntimeError("Prompt projection surface graph effects are unwired.")
        return self._bindings


def bind_prompt_projection_surface_graph_effects(
    effects: PromptProjectionSurfaceGraphEffects,
    *,
    freshness: PromptProjectionFreshnessController,
    autocomplete: PromptAutocompletePreviewProjectionOwner,
    lifecycle: PromptProjectionSurfaceLifecycleRuntime,
    presentation: PromptProjectionSurfacePresentationRuntime,
) -> None:
    """Bind graph effects to the completed projection owner graph."""

    caret_visual = lifecycle.caret_visual
    effects.bind(
        PromptProjectionSurfaceGraphEffectBindings(
            projection_is_stale=freshness.has_stale_projection_geometry,
            rebuild_projection=lambda: presentation.rebuild.rebuild(),
            reconcile_autocomplete=(
                lambda cursor, selection_is_empty: (
                    autocomplete.reconcile_after_caret_state_change(
                        cursor_position=cursor,
                        selection_is_empty=selection_is_empty,
                    )
                )
            ),
            refresh_active_projection=(
                lambda: presentation.active_projection.reconcile_current_active_span()
            ),
            ensure_caret_visible=lambda: caret_visual.ensure_caret_visible(),
            refresh_caret_layers=(
                lambda: presentation.render_publication.caret_changed()
            ),
            refresh_deferred_caret_layers=(
                lambda: presentation.render_publication.deferred_caret_changed()
            ),
            restart_caret_blink=(
                lambda: caret_visual.restart_caret_blink_cycle(
                    cursor_flash_time_ms=caret_visual.cursor_flash_time_ms()
                )
            ),
            update_caret_paint=caret_visual.update_caret_paint,
            diagnostic_layer_changed=(
                lambda: presentation.render_publication.diagnostic_layer_changed()
            ),
            rebuild_active_projection=(
                lambda: presentation.active_projection.rebuild()
            ),
            prepare_focus_chrome=(
                lambda: presentation.render_publication.prepare_focus_chrome()
            ),
            schedule_caret_blink=(
                lambda reset_cycle: caret_visual.schedule_caret_blink_sync(
                    reset_cycle=reset_cycle,
                    cursor_flash_time_ms=caret_visual.cursor_flash_time_ms,
                )
            ),
            is_projected=(
                lambda: (
                    presentation.rebuild.display_mode
                    is PromptProjectionDisplayMode.PROJECTED
                )
            ),
            apply_session_paint_state=(
                lambda: (
                    presentation.active_projection.try_apply_current_session_paint_state()
                )
            ),
        )
    )


__all__ = [
    "PromptProjectionSurfaceGraphEffectBindings",
    "PromptProjectionSurfaceGraphEffects",
    "bind_prompt_projection_surface_graph_effects",
]
