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

"""Apply concrete Output image routes through the guarded projector."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
    OutputRouteProjectorPort,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.presentation.canvas.output.output_route_binding_controller import (
    OutputRouteBindingController,
)


@dataclass(frozen=True, slots=True)
class OutputImageRouteController:
    """Own user-selected and projection-selected concrete image commands."""

    route_binding: OutputRouteBindingController
    route_projector: OutputRouteProjectorPort

    def set_current_image(self, image_id: UUID | None) -> bool:
        """Bind and apply a user-selected concrete image or empty route."""

        route = (
            CanvasRouteIdentity.empty()
            if image_id is None
            else CanvasRouteIdentity(
                route_kind="output_image",
                route_key=f"image:{image_id}",
                primary_image_id=image_id,
            )
        )
        self.route_binding.bind_output_route(route)
        if image_id is None:
            return bool(self.route_projector.clear_route(route))
        return bool(self.route_projector.apply_final_image_route(route, image_id))

    def apply_projection_image(
        self,
        session: OutputCanvasSession,
        image_id: UUID,
    ) -> bool:
        """Apply a final image through the projection session's active route."""

        return bool(
            self.route_projector.apply_final_image_route(
                session.active_route,
                image_id,
            )
        )


__all__ = ["OutputImageRouteController"]
