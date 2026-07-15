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

"""Synchronize Output compare rendering through the QPane compare presenter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.presentation.canvas.output.output_compare_presenter import (
    OutputComparePresentation,
)


class OutputCompareClearProjector(Protocol):
    """Clear compare rendering for one authorized Output route."""

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Clear the active compare rendering for route."""


class OutputCompareRenderer(Protocol):
    """Present reconciled compare state through a route projector."""

    def present(
        self,
        *,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
        route_blocked: bool = False,
    ) -> OutputComparePresentation:
        """Return the compare presentation result for one projection."""


@dataclass(frozen=True, slots=True)
class OutputCanvasCompareRenderingController:
    """Own Output compare presentation and QPane compare clearing."""

    visible_compare_state: Callable[[], OutputCompareState]
    output_projection: Callable[[], OutputCanvasProjection | None]
    output_compare_presenter: Callable[[], OutputCompareRenderer]
    route_blocked: Callable[[], bool]
    set_visible_compare_state: Callable[[OutputCompareState], None]
    emit_compare_changed: Callable[[OutputCompareState], None]
    clear_route_identity: Callable[[], CanvasRouteIdentity]
    bind_output_route_projector: Callable[[CanvasRouteIdentity], None]
    route_projector: Callable[[], OutputCompareClearProjector]

    def sync_compare_rendering(self) -> None:
        """Apply current compare state to QPane or clear comparison rendering."""

        state = self.visible_compare_state()
        projection = self.output_projection()
        if projection is None:
            self.clear_pane_comparison()
            return
        presentation = self.output_compare_presenter().present(
            projection=projection,
            state=state,
            route_blocked=self.route_blocked(),
        )
        if presentation.state != state:
            self.set_visible_compare_state(presentation.state)
            self.emit_compare_changed(presentation.state)

    def clear_pane_comparison(self) -> None:
        """Clear QPane comparison rendering when the API is available."""

        route = self.clear_route_identity()
        self.bind_output_route_projector(route)
        self.route_projector().clear_compare(route=route)


__all__ = [
    "OutputCanvasCompareRenderingController",
    "OutputCompareClearProjector",
    "OutputCompareRenderer",
]
