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

"""Own late-bound source effects across the projection composition cycle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .surface_lifecycle_runtime import PromptProjectionSurfaceLifecycleRuntime
    from .surface_presentation_runtime import PromptProjectionSurfacePresentationRuntime


@dataclass(frozen=True, slots=True)
class PromptProjectionSourceLifecycleEffectBindings:
    """Declare source effects implemented by source-ready projection owners."""

    ensure_caret_visible: Callable[[], None]
    rebuild_projection: Callable[[], None]
    publish_active_span_range: Callable[[tuple[int, int] | None], None]
    reconcile_committed_active_projection: Callable[[], None]
    rebuild_active_projection: Callable[[bool], None]
    clear_reorder_for_source_change: Callable[[], None]
    invalidate_render_for_source_change: Callable[[bool], None]


class PromptProjectionSourceLifecycleEffects:
    """Expose source effects only after their authoritative owners exist."""

    def __init__(self) -> None:
        """Create an explicitly unwired source-effect port."""

        self._bindings: PromptProjectionSourceLifecycleEffectBindings | None = None

    def bind(
        self,
        bindings: PromptProjectionSourceLifecycleEffectBindings,
    ) -> None:
        """Bind every source effect once after lifecycle composition completes."""

        if self._bindings is not None:
            raise RuntimeError("Prompt projection source lifecycle effects are wired.")
        self._bindings = bindings

    def ensure_caret_visible(self) -> None:
        """Ensure the current caret is visible through the visual owner."""

        self._require_bindings().ensure_caret_visible()

    def rebuild_projection(self) -> None:
        """Rebuild the committed projection through the presentation owner."""

        self._require_bindings().rebuild_projection()

    def publish_active_span_range(self, value: tuple[int, int] | None) -> None:
        """Publish the rendered active span through the active projection owner."""

        self._require_bindings().publish_active_span_range(value)

    def reconcile_committed_active_projection(self) -> None:
        """Adopt committed state unless transient geometry remains authoritative."""

        self._require_bindings().reconcile_committed_active_projection()

    def rebuild_active_projection(self, commit_projection: bool) -> None:
        """Rebuild active-projection state with the requested commit policy."""

        self._require_bindings().rebuild_active_projection(commit_projection)

    def clear_reorder_for_source_change(self) -> None:
        """Clear reorder state before publishing a source change."""

        self._require_bindings().clear_reorder_for_source_change()

    def invalidate_render_for_source_change(
        self,
        clear_diagnostic_fragment_cache: bool,
    ) -> None:
        """Invalidate render state for a newly published source revision."""

        self._require_bindings().invalidate_render_for_source_change(
            clear_diagnostic_fragment_cache
        )

    def _require_bindings(self) -> PromptProjectionSourceLifecycleEffectBindings:
        """Return bound effects or reject invalid construction-time dispatch."""

        if self._bindings is None:
            raise RuntimeError(
                "Prompt projection source lifecycle effects are unwired."
            )
        return self._bindings


def bind_prompt_projection_source_lifecycle_effects(
    effects: PromptProjectionSourceLifecycleEffects,
    *,
    lifecycle: PromptProjectionSurfaceLifecycleRuntime,
    presentation: PromptProjectionSurfacePresentationRuntime,
) -> None:
    """Bind source effects to the completed lifecycle and presentation graph."""

    effects.bind(
        PromptProjectionSourceLifecycleEffectBindings(
            ensure_caret_visible=lambda: lifecycle.caret_visual.ensure_caret_visible(),
            rebuild_projection=lambda: presentation.rebuild.rebuild(),
            publish_active_span_range=(
                lambda value: (
                    presentation.active_projection.publish_rendered_active_span_range(
                        value
                    )
                )
            ),
            reconcile_committed_active_projection=(
                lambda: presentation.active_projection.reconcile_committed_projection()
            ),
            rebuild_active_projection=(
                lambda commit: presentation.active_projection.rebuild(
                    commit_projection=commit
                )
            ),
            clear_reorder_for_source_change=(
                lambda: lifecycle.reorder.clear_for_source_change()
            ),
            invalidate_render_for_source_change=(
                lambda clear_fragment_cache: (
                    presentation.render_publication.source_changed(
                        clear_diagnostic_fragment_cache=clear_fragment_cache
                    )
                )
            ),
        )
    )


__all__ = [
    "PromptProjectionSourceLifecycleEffectBindings",
    "PromptProjectionSourceLifecycleEffects",
    "bind_prompt_projection_source_lifecycle_effects",
]
