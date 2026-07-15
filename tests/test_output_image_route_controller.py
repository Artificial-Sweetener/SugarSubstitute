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

"""Verify guarded concrete Output image route commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.presentation.canvas.output.output_image_route_controller import (
    OutputImageRouteController,
)


def test_selected_image_binds_before_projector_application() -> None:
    """A concrete image command should authorize its route before applying it."""

    image_id = uuid4()
    events: list[object] = []
    binding = _RouteBinding(events)
    projector = _Projector(events)

    accepted = OutputImageRouteController(
        cast(Any, binding), cast(Any, projector)
    ).set_current_image(image_id)

    route = CanvasRouteIdentity("output_image", f"image:{image_id}", image_id)
    assert accepted is True
    assert events == [("bind", route), ("apply", route, image_id)]


def test_none_binds_and_clears_empty_route() -> None:
    """Clearing selection should bind and clear the canonical empty route."""

    events: list[object] = []
    controller = OutputImageRouteController(
        cast(Any, _RouteBinding(events)),
        cast(Any, _Projector(events)),
    )

    assert controller.set_current_image(None) is True
    assert events == [
        ("bind", CanvasRouteIdentity.empty()),
        ("clear", CanvasRouteIdentity.empty()),
    ]


@dataclass(slots=True)
class _RouteBinding:
    """Record authorization ordering."""

    events: list[object]

    def bind_output_route(self, route: CanvasRouteIdentity) -> None:
        """Record one route binding."""

        self.events.append(("bind", route))


@dataclass(slots=True)
class _Projector:
    """Record concrete projector commands."""

    events: list[object] = field(default_factory=list)

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Record one image application."""

        self.events.append(("apply", route, image_id))
        return True

    def clear_route(self, route: CanvasRouteIdentity) -> bool:
        """Record one empty-route clear."""

        self.events.append(("clear", route))
        return True
