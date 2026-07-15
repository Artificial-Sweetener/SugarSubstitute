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

"""Coalesce Output viewport changes into stale-safe responsive grid reflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.domain.workflow import CanvasSessionToken
from substitute.presentation.canvas.output.output_grid_reflow_context import (
    OutputGridReflowContextResolver,
    OutputSceneOverviewGridContext,
    OutputSourceGridContext,
)
from substitute.presentation.canvas.output.output_grid_route_application_controller import (
    OutputGridRouteApplicationController,
)
from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridLayoutSignature,
    OutputGridScenePlan,
)
from substitute.presentation.canvas.output.output_scene_overview_composer import (
    OutputSceneOverviewComposer,
)
from substitute.presentation.canvas.output.output_source_grid_composer import (
    OutputSourceGridComposer,
)
from substitute.presentation.canvas.shared.responsive_canvas_grid_policy import (
    CanvasViewportExtent,
)

logger = logging.getLogger(__name__)


class ReflowTimer(Protocol):
    """Expose the single-shot timer operations needed for frame coalescing."""

    def start(self, interval_ms: int) -> None:
        """Start or restart timer delivery."""

    def stop(self) -> None:
        """Cancel pending delivery."""

    def isActive(self) -> bool:  # noqa: N802
        """Return whether delivery is already pending."""


@dataclass(frozen=True, slots=True)
class OutputGridPresentationSignature:
    """Identify one session-bound applied grid layout."""

    session_token: CanvasSessionToken
    layout: OutputGridLayoutSignature


@dataclass(frozen=True, slots=True)
class _PendingReflow:
    """Capture the latest viewport and session at scheduling time."""

    viewport: CanvasViewportExtent
    session_token: CanvasSessionToken
    generation: int


class OutputGridReflowController:
    """Own viewport coalescing, stale rejection, and layout deduplication."""

    def __init__(
        self,
        *,
        timer: ReflowTimer,
        context_resolver: OutputGridReflowContextResolver,
        source_composer: OutputSourceGridComposer,
        scene_composer: OutputSceneOverviewComposer,
        route_application: OutputGridRouteApplicationController,
    ) -> None:
        """Store responsive grid collaborators and initialize derived state."""

        self._timer = timer
        self._context_resolver = context_resolver
        self._source_composer = source_composer
        self._scene_composer = scene_composer
        self._route_application = route_application
        self._pending: _PendingReflow | None = None
        self._generation = 0
        self._last_applied: OutputGridPresentationSignature | None = None

    def on_viewport_rect_changed(self, rect: object) -> None:
        """Capture the latest valid physical viewport and coalesce delivery."""

        viewport = _viewport_extent(rect)
        context = self._context_resolver.current_context()
        if viewport is None or context is None:
            return
        self._generation += 1
        self._pending = _PendingReflow(
            viewport, context.session_token, self._generation
        )
        logger.debug(
            "Scheduled Output grid reflow",
            extra=_log_context(context, viewport, reason="viewport_changed"),
        )
        if not self._timer.isActive():
            self._timer.start(16)
        else:
            logger.debug(
                "Coalesced Output grid reflow",
                extra=_log_context(context, viewport, reason="timer_active"),
            )

    def deliver_pending(self) -> None:
        """Present only the newest coalesced viewport request."""

        pending = self._pending
        self._pending = None
        if pending is None:
            return
        self._present(
            pending.viewport,
            captured_token=pending.session_token,
            activate=True,
        )

    def present_current_grid(self, viewport: CanvasViewportExtent) -> bool:
        """Immediately present the current grid through the same guarded path."""

        self._generation += 1
        self._pending = None
        self._timer.stop()
        context = self._context_resolver.current_context()
        if context is None:
            self._last_applied = None
            return False
        return self._present(
            viewport, captured_token=context.session_token, activate=True
        )

    def cancel(self) -> None:
        """Cancel derived pending grid work without mutating QPane catalog state."""

        previous = self._last_applied
        self._generation += 1
        self._pending = None
        self._last_applied = None
        self._timer.stop()
        token = previous.session_token if previous is not None else None
        dimensions = previous.layout.dimensions if previous is not None else None
        logger.debug(
            "Canceled Output grid reflow",
            extra={
                "workflow_id": token.workflow_id.value if token is not None else None,
                "session_revision": (
                    token.revision.value if token is not None else None
                ),
                "route_kind": (
                    token.active_route.route_kind if token is not None else None
                ),
                "route_key": (
                    token.active_route.route_key if token is not None else None
                ),
                "source_key": None,
                "tile_count": None,
                "columns": dimensions[0] if dimensions is not None else None,
                "rows": dimensions[1] if dimensions is not None else None,
                "viewport_width": None,
                "viewport_height": None,
                "reason": "route_left",
            },
        )

    def _present(
        self,
        viewport: CanvasViewportExtent,
        *,
        captured_token: CanvasSessionToken,
        activate: bool,
    ) -> bool:
        """Build and apply a fresh current plan when session and signature allow."""

        context = self._context_resolver.current_context()
        if context is None or context.session_token != captured_token:
            logger.warning(
                "Rejected stale Output grid reflow request",
                extra={
                    "workflow_id": captured_token.workflow_id.value,
                    "session_revision": captured_token.revision.value,
                    "route_kind": captured_token.active_route.route_kind,
                    "route_key": captured_token.active_route.route_key,
                    "viewport_width": viewport.width,
                    "viewport_height": viewport.height,
                    "reason": "stale_session_token",
                },
            )
            return False
        first_plan = self._compose(context, viewport, previous_dimensions=None)
        if first_plan is None:
            logger.warning(
                "Output grid reflow could not build a current scene plan",
                extra=_log_context(context, viewport, reason="invalid_grid_context"),
            )
            return False
        previous = self._last_applied
        plan = first_plan
        if (
            previous is not None
            and previous.session_token == context.session_token
            and previous.layout.content == first_plan.layout_signature.content
        ):
            retained = self._compose(
                context,
                viewport,
                previous_dimensions=previous.layout.dimensions,
            )
            if retained is not None:
                plan = retained
        signature = OutputGridPresentationSignature(
            context.session_token, plan.layout_signature
        )
        if signature == self._last_applied:
            logger.debug(
                "Skipped unchanged Output grid reflow",
                extra=_log_context(
                    context,
                    viewport,
                    reason="unchanged_signature",
                    dimensions=plan.layout_signature.dimensions,
                ),
            )
            return True
        result = self._route_application.apply(plan, activate=activate)
        if not result.accepted:
            logger.warning(
                "Output grid reflow route application was rejected",
                extra=_log_context(
                    context,
                    viewport,
                    reason=result.rejection_reason or "route_application_rejected",
                    dimensions=plan.layout_signature.dimensions,
                ),
            )
            return False
        self._last_applied = signature
        logger.debug(
            "Applied Output grid reflow",
            extra=_log_context(
                context,
                viewport,
                reason="applied",
                dimensions=plan.layout_signature.dimensions,
            ),
        )
        return True

    def _compose(
        self,
        context: OutputSceneOverviewGridContext | OutputSourceGridContext,
        viewport: CanvasViewportExtent,
        *,
        previous_dimensions: tuple[int, int] | None,
    ) -> OutputGridScenePlan | None:
        """Delegate tile selection to the specialized current grid composer."""

        if isinstance(context, OutputSceneOverviewGridContext):
            return self._scene_composer.compose_scene_overview(
                context.scenes,
                active_scene_key=context.route.route_key.removeprefix("scene:") or None,
                previous_dimensions=previous_dimensions,
                viewport_extent=viewport,
            )
        return self._source_composer.compose_source_grid(
            context.source,
            scene_key=context.scene_key,
            previous_dimensions=previous_dimensions,
            viewport_extent=viewport,
        )


def _viewport_extent(rect: object) -> CanvasViewportExtent | None:
    """Normalize a QRectF-like object into a valid physical viewport extent."""

    width_value = getattr(rect, "width", None)
    height_value = getattr(rect, "height", None)
    try:
        width = float(
            cast(float, width_value() if callable(width_value) else width_value)
        )
        height = float(
            cast(float, height_value() if callable(height_value) else height_value)
        )
    except (TypeError, ValueError):
        return None
    viewport = CanvasViewportExtent(width, height)
    return viewport if viewport.valid else None


def _log_context(
    context: OutputSceneOverviewGridContext | OutputSourceGridContext,
    viewport: CanvasViewportExtent,
    *,
    reason: str,
    dimensions: tuple[int, int] | None = None,
) -> dict[str, object]:
    """Return structured diagnostic context without payload or path data."""

    tile_count = (
        len(context.scenes)
        if isinstance(context, OutputSceneOverviewGridContext)
        else len(context.source.images_by_set)
    )
    return {
        "workflow_id": context.session_token.workflow_id.value,
        "session_revision": context.session_token.revision.value,
        "route_kind": context.route.route_kind,
        "route_key": context.route.route_key,
        "source_key": (
            context.source.source_key
            if isinstance(context, OutputSourceGridContext)
            else None
        ),
        "tile_count": tile_count,
        "columns": dimensions[0] if dimensions is not None else None,
        "rows": dimensions[1] if dimensions is not None else None,
        "viewport_width": viewport.width,
        "viewport_height": viewport.height,
        "reason": reason,
    }


__all__ = [
    "OutputGridPresentationSignature",
    "OutputGridReflowController",
    "ReflowTimer",
]
