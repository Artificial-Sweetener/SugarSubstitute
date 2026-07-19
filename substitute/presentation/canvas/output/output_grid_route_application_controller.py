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

"""Apply prepared Output grid scene plans through guarded QPane routing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)

from substitute.presentation.canvas.output.output_grid_scene_builder import (
    OutputGridLayoutSignature,
    OutputGridScenePlan,
)


class OutputRouteApplicationProjector(Protocol):
    """Apply prepared Output grid routes and resolve composition identity."""

    def apply_source_grid_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Apply one source-grid request."""

    def apply_scene_overview_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Apply one scene-overview request."""

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Return the deterministic composition identity for route."""


@dataclass(frozen=True, slots=True)
class OutputGridApplicationResult:
    """Describe one accepted or rejected prepared grid application."""

    accepted: bool
    composition_id: UUID | None = None
    layout_signature: OutputGridLayoutSignature | None = None
    rejection_reason: str | None = None


@dataclass(frozen=True, slots=True)
class OutputGridRouteApplicationController:
    """Prepare catalog images and apply one typed grid scene plan."""

    route_projector: OutputRouteApplicationProjector
    ensure_scene_request_images_cached: Callable[[object], bool]

    def apply(
        self, plan: OutputGridScenePlan, *, activate: bool
    ) -> OutputGridApplicationResult:
        """Apply a prepared source or scene grid through guarded routing."""

        if not self.ensure_scene_request_images_cached(plan.request):
            return OutputGridApplicationResult(
                accepted=False,
                rejection_reason="catalog_preparation_failed",
            )
        if plan.route.route_kind == "source_grid":
            accepted = self.route_projector.apply_source_grid_route(
                plan.route, plan.request, activate=activate
            )
        elif plan.route.route_kind == "scene_overview":
            accepted = self.route_projector.apply_scene_overview_route(
                plan.route, plan.request, activate=activate
            )
        else:
            return OutputGridApplicationResult(
                accepted=False,
                rejection_reason="invalid_route",
            )
        if not accepted:
            return OutputGridApplicationResult(
                accepted=False,
                rejection_reason="projector_rejected",
            )
        result = OutputGridApplicationResult(
            accepted=True,
            composition_id=self.route_projector.route_composition_id(plan.route),
            layout_signature=plan.layout_signature,
        )
        return result


__all__ = [
    "OutputGridApplicationResult",
    "OutputGridRouteApplicationController",
    "OutputRouteApplicationProjector",
]
