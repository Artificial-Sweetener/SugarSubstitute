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

"""Coordinate the separated Output projection lifecycle collaborators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_compare_state import OutputCompareState
from substitute.application.workflows.output_preview_lifecycle_service import (
    PreviewSlotKey,
)
from substitute.presentation.canvas.output.output_compare_projection_presenter import (
    OutputCompareProjectionPresenter,
)
from substitute.presentation.canvas.output.output_image_route_controller import (
    OutputImageRouteController,
)
from substitute.presentation.canvas.output.output_projection_presenter import (
    OutputProjectionPresenter,
)
from substitute.presentation.canvas.output.output_route_binding_controller import (
    OutputRouteBindingController,
)


@dataclass(frozen=True, slots=True)
class OutputCanvasProjectionController:
    """Expose the host-facing projection lifecycle as a small typed facade."""

    route_binding: OutputRouteBindingController
    image_routes: OutputImageRouteController
    presenter: OutputProjectionPresenter
    compare_presenter: OutputCompareProjectionPresenter

    def bind_output_route_projector(self, route: CanvasRouteIdentity) -> None:
        """Bind the current Output display scope to route."""

        self.route_binding.bind_output_route(route)

    def bind_projection_route_projector(self, session: OutputCanvasSession) -> None:
        """Bind the projector to an exact application projection session."""

        self.route_binding.bind_projection_session(session)

    def bind_projection_session(
        self,
        session: OutputCanvasSession,
        *,
        retire_completed_preview_slot: Callable[[PreviewSlotKey, str, str], None],
    ) -> None:
        """Present one authorized Output projection session."""

        self.presenter.present_session(
            session,
            retire_completed_preview_slot=retire_completed_preview_slot,
        )

    def adopt_missing_projection_session(self, session: OutputCanvasSession) -> None:
        """Adopt and bind an application-minted projection session."""

        self.route_binding.bind_projection_session(session)

    def set_current_output_image(self, image_id: UUID | None) -> bool:
        """Apply a user-selected concrete image or empty route."""

        return self.image_routes.set_current_image(image_id)

    def apply_projection_final_image(
        self,
        session: OutputCanvasSession,
        image_id: UUID,
    ) -> bool:
        """Apply a final image from the active projection session."""

        return self.image_routes.apply_projection_image(session, image_id)

    def sync_compare_projection(
        self,
        projection: OutputCanvasProjection,
        state: OutputCompareState,
    ) -> None:
        """Apply one compare projection plan through its presenter."""

        self.compare_presenter.present(projection, state)

    def route_targets_preview_lane(
        self,
        session: OutputCanvasSession,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether route targets an accepted session preview."""

        return self.route_binding.route_targets_preview_lane(session, route)


__all__ = ["OutputCanvasProjectionController"]
