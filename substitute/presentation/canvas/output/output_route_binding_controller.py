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

"""Bind authorized Output routes to the current canvas session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasRouteSessionBoundaryPort,
    OutputRouteProjectorPort,
    OutputRouteScope,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_route_scope import (
    output_route_scope_members,
    route_targets_preview_lane,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OutputRouteBindingState:
    """Expose the narrow mutable state required for route authorization."""

    workflow_id: Callable[[], str]
    projection: Callable[[], OutputCanvasProjection | None]
    session: Callable[[], OutputCanvasSession | None]
    store_session: Callable[[OutputCanvasSession], None]
    preview_registry: Callable[[], OutputPreviewRegistry]
    active_scene_overview: Callable[[], bool]
    active_scene_key: Callable[[], str | None]


@dataclass(frozen=True, slots=True)
class OutputRouteBindingController:
    """Own Output session adoption, route scopes, and projector binding."""

    route_projector: OutputRouteProjectorPort
    session_boundary: CanvasRouteSessionBoundaryPort
    state: OutputRouteBindingState

    def bind_output_route(self, route: CanvasRouteIdentity) -> OutputCanvasSession:
        """Bind a user-selected route against the current projection membership."""

        session = self.state.session()
        if (
            session is not None
            and (
                session.active_route == route
                or self.route_targets_preview_lane(session, route)
            )
            and self._current_boundary_session() == session.session
        ):
            self._bind_scope(session, route)
            return session

        projection = self.state.projection() or OutputCanvasProjection(
            sources=(),
            active_source_key=None,
            active_set_index=1,
            active_uuid=None,
            set_count=0,
        )
        session = bind_output_canvas_session(
            self.session_boundary,
            workflow_id=self.state.workflow_id(),
            projection=projection,
            image_metadata_lookup={
                item.image_id: item.image_meta
                for source in projection.sources
                for item in source.images_by_set.values()
            },
        )
        self.state.store_session(session)
        self._bind_scope(session, route)
        return session

    def bind_projection_session(self, session: OutputCanvasSession) -> None:
        """Adopt and bind the exact route carried by a projection session."""

        self._adopt_projection_session(session)
        self._bind_scope(session, session.active_route)

    def route_targets_preview_lane(
        self,
        session: OutputCanvasSession,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether route targets an accepted preview in session."""

        return route_targets_preview_lane(
            route,
            self.state.preview_registry().lanes_for_session(session),
        )

    def _adopt_projection_session(self, session: OutputCanvasSession) -> None:
        """Adopt an application-minted session through the public boundary API."""

        if self.session_boundary.adopt_session(session.session):
            return
        logger.warning(
            "Rejected Output projection session adoption",
            extra={
                "workflow_id": session.workflow_id.value,
                "canvas_kind": session.canvas_kind.value,
                "session_revision": session.revision.value,
            },
        )

    def _bind_scope(
        self,
        session: OutputCanvasSession,
        route: CanvasRouteIdentity,
    ) -> None:
        """Bind QPane to the authorized members of one Output route."""

        members = output_route_scope_members(
            session=session,
            route=route,
            preview_lanes=self.state.preview_registry().lanes_for_session(session),
            active_scene_overview=self.state.active_scene_overview(),
            active_scene_key=self.state.active_scene_key(),
        )
        self.route_projector.bind(
            OutputRouteScope(
                session=session,
                allowed_image_ids=members.image_ids,
                allowed_source_keys=members.source_keys,
                allowed_scene_keys=members.scene_keys,
                allowed_composition_ids=members.composition_ids,
            )
        )

    def _current_boundary_session(self) -> object | None:
        """Return the current Output boundary session when available."""

        return self.session_boundary.current_session(CanvasKind.OUTPUT)


__all__ = ["OutputRouteBindingController", "OutputRouteBindingState"]
