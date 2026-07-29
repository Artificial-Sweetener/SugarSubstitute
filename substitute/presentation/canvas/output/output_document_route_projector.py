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

"""Authorize Output document routes without depending on legacy presentation APIs."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasRouteSessionBoundaryPort,
    CanvasSessionRejectionReason,
    OutputCanvasHitValidation,
    OutputRouteScope,
)
from substitute.application.workflows.output_canvas_route_scope import (
    route_source_and_scene,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.output.output_document_route_projector")


class OutputDocumentRouteDisplayPort(Protocol):
    """Describe authorized document presentation commands for Output routes."""

    def present_single(self, image_id: UUID) -> bool:
        """Present one application Output image."""

    def present_comparison(
        self,
        primary_image_id: UUID,
        secondary_image_id: UUID,
        *,
        split_position: float,
        orientation: str,
    ) -> bool:
        """Present two application Output images in reveal comparison."""

    def clear_presentation(self) -> None:
        """Clear active Output presentation targets."""

    def image_id_for_composition(self, composition_id: UUID) -> UUID | None:
        """Resolve a visible document composition to application identity."""

    @property
    def session(self) -> object:
        """Return view state that exposes active_composition_id."""


class OutputDocumentRouteProjector:
    """Guard Output document presentation mutations behind the active session."""

    def __init__(
        self,
        display: OutputDocumentRouteDisplayPort,
        *,
        session_boundary: CanvasRouteSessionBoundaryPort,
    ) -> None:
        """Store the document display port and application session authority."""

        self._display = display
        self._session_boundary = session_boundary
        self._scope: OutputRouteScope | None = None

    def bind(self, scope: OutputRouteScope) -> None:
        """Bind one active Output authorization scope."""

        self._scope = scope
        composition_id = getattr(self._display.session, "active_composition_id", None)
        current_image_id = (
            self._display.image_id_for_composition(composition_id)
            if isinstance(composition_id, UUID)
            else None
        )
        if (
            current_image_id is not None
            and current_image_id not in scope.allowed_image_ids
        ):
            self._display.clear_presentation()

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Present one authorized Output image composition."""

        scope = self._scope
        if not self._authorize(scope, route, image_id):
            return False
        assert scope is not None
        if not self._route_may_activate(scope, route):
            self._log_rejection(route, image_id, "inactive_route_activation")
            return False
        if route.route_kind != "output_image" or route.primary_image_id != image_id:
            self._log_rejection(route, image_id, "route_image_mismatch")
            return False
        if image_id not in scope.allowed_image_ids:
            self._log_rejection(route, image_id, "foreign_image")
            return False
        if not self._route_is_allowed(scope, route):
            self._log_rejection(route, image_id, "foreign_route")
            return False
        return self._display.present_single(image_id)

    def apply_source_grid_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Reject retired synthetic-grid requests at the document boundary."""

        del request, activate
        self._log_rejection(route, None, "legacy_grid_request")
        return False

    def apply_scene_overview_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Reject retired synthetic-overview requests at the document boundary."""

        del request, activate
        self._log_rejection(route, None, "legacy_scene_request")
        return False

    def clear_route(self, route: CanvasRouteIdentity) -> bool:
        """Clear Output presentation when the current scope authorizes route."""

        if not self._authorize(self._scope, route, None):
            return False
        scope = self._scope
        assert scope is not None
        if not self._route_is_allowed(scope, route):
            self._log_rejection(route, None, "foreign_route")
            return False
        self._display.clear_presentation()
        return True

    def current_image_id_for_event(self) -> UUID | None:
        """Return the visible image only when the current scope authorizes it."""

        scope = self._scope
        if scope is None:
            return None
        if not self._authorize(scope, scope.session.active_route, None):
            return None
        composition_id = getattr(self._display.session, "active_composition_id", None)
        if not isinstance(composition_id, UUID):
            return None
        image_id = self._display.image_id_for_composition(composition_id)
        if image_id is None or image_id in scope.allowed_image_ids:
            return image_id
        self._log_rejection(
            scope.session.active_route, image_id, "foreign_current_image"
        )
        return None

    def is_image_allowed_for_transfer(self, image_id: UUID) -> bool:
        """Return whether the current Output session still authorizes one image."""

        scope = self._scope
        if scope is None or image_id not in scope.allowed_image_ids:
            return False
        return self._authorize(scope, scope.session.active_route, image_id)

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Reject the removed synthetic composition identity model."""

        del route
        raise RuntimeError("Output grid routes are document presentations")

    def apply_compare(
        self,
        *,
        route: CanvasRouteIdentity,
        base_image_id: UUID,
        comparison_image_id: UUID,
        split_position: float,
        orientation: object,
    ) -> bool:
        """Present one authorized document reveal comparison."""

        scope = self._scope
        if not self._authorize(scope, route, base_image_id):
            return False
        assert scope is not None
        if (
            not self._route_may_activate(scope, route)
            or not self._route_is_allowed(scope, route)
            or base_image_id not in scope.allowed_image_ids
            or comparison_image_id not in scope.allowed_image_ids
        ):
            self._log_rejection(route, base_image_id, "foreign_compare_route")
            return False
        orientation_value = str(getattr(orientation, "value", orientation))
        return self._display.present_comparison(
            base_image_id,
            comparison_image_id,
            split_position=split_position,
            orientation=orientation_value,
        )

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Authorize comparison cleanup without clearing the broader linked group."""

        if not self._authorize(self._scope, route, None):
            return False
        scope = self._scope
        assert scope is not None
        if not self._route_is_allowed(scope, route):
            self._log_rejection(route, None, "foreign_route")
            return False
        return True

    def validate_scene_hit(self, hit: object) -> OutputCanvasHitValidation:
        """Reject retired scene-hit payloads at the document boundary."""

        del hit
        return OutputCanvasHitValidation.rejected("legacy_scene_hit")

    def hit_test_scene(self, point: object) -> OutputCanvasHitValidation:
        """Reject retired scene hit-testing at the document boundary."""

        del point
        return OutputCanvasHitValidation.rejected("legacy_scene_hit")

    def _authorize(
        self,
        scope: OutputRouteScope | None,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
    ) -> bool:
        """Return whether scope remains the current Output display authority."""

        if scope is None:
            self._log_rejection(route, image_id, "missing_scope")
            return False
        authorization = self._session_boundary.authorize_display_mutation(
            scope.session.token(), canvas_kind=CanvasKind.OUTPUT
        )
        if authorization.accepted:
            return True
        reason = (
            authorization.rejection_reason
            or CanvasSessionRejectionReason.MISSING_SESSION
        )
        self._log_rejection(route, image_id, reason.value)
        return False

    @staticmethod
    def _route_may_activate(
        scope: OutputRouteScope,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether route is the active route or accepted preview image route."""

        return route == scope.session.active_route or (
            route.route_kind == "output_image"
            and route.primary_image_id in scope.allowed_image_ids
            and route.primary_image_id not in scope.session.allowed_image_ids
        )

    @staticmethod
    def _route_is_allowed(
        scope: OutputRouteScope,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether encoded source and scene keys belong to current scope."""

        source_key, scene_key = route_source_and_scene(route)
        return (source_key is None or source_key in scope.allowed_source_keys) and (
            scene_key is None or not scene_key or scene_key in scope.allowed_scene_keys
        )

    def _log_rejection(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        reason: str,
    ) -> None:
        """Log one prompt-safe rejected Output document route command."""

        scope = self._scope
        log_warning(
            _LOGGER,
            "Output document route command rejected",
            workflow_id=scope.session.workflow_id.value if scope is not None else "",
            canvas_kind=CanvasKind.OUTPUT.value,
            route_kind=route.route_kind,
            route_key=route.route_key,
            requested_image_id=image_id,
            rejection_reason=reason,
        )


__all__ = ["OutputDocumentRouteDisplayPort", "OutputDocumentRouteProjector"]
