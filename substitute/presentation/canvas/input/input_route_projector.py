#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Authorize Input document routes independently of a canvas implementation."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasRouteSessionBoundaryPort,
    CanvasSessionRejectionReason,
    InputRouteScope,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_route_projector")


class InputRouteDisplayPort(Protocol):
    """Describe document display commands needed by the Input route boundary."""

    def set_current_image_id(self, image_id: UUID | None) -> bool:
        """Show one application image identity or clear the active presentation."""

    def current_image_id(self) -> UUID | None:
        """Return the application identity currently visible to the user."""

    def set_active_mask_id(self, mask_id: UUID) -> bool:
        """Activate a mask already belonging to the visible image."""


class InputRouteProjector:
    """Guard Input document display mutations behind the active route session."""

    def __init__(
        self,
        display: InputRouteDisplayPort,
        *,
        session_boundary: CanvasRouteSessionBoundaryPort,
    ) -> None:
        """Store the sole display port and application session boundary."""

        self._display = display
        self._session_boundary = session_boundary
        self._scope: InputRouteScope | None = None

    def bind(self, scope: InputRouteScope) -> None:
        """Bind the current Input route scope."""

        self._scope = scope

    def show_image(self, image_id: UUID | None) -> bool:
        """Show an authorized image identity."""

        scope = self._scope
        if scope is None:
            self._log_rejection(CanvasRouteIdentity.empty(), image_id, "missing_scope")
            return False
        if not self._authorize(scope, scope.session.active_route, image_id):
            return False
        if image_id is not None and image_id not in scope.allowed_image_ids:
            self._log_rejection(scope.session.active_route, image_id, "foreign_image")
            return False
        if self._display.current_image_id() == image_id:
            return True
        return self._display.set_current_image_id(image_id)

    def show_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Show an authorized image and activate its authorized mask."""

        scope = self._scope
        if scope is None:
            self._log_rejection(
                CanvasRouteIdentity.empty(), image_id, "missing_scope", mask_id
            )
            return False
        if not self._authorize(scope, scope.session.active_route, image_id, mask_id):
            return False
        if image_id not in scope.allowed_image_ids:
            self._log_rejection(
                scope.session.active_route, image_id, "foreign_image", mask_id
            )
            return False
        if scope.allowed_mask_image_ids.get(mask_id) != image_id:
            self._log_rejection(
                scope.session.active_route, image_id, "foreign_mask", mask_id
            )
            return False
        return self.show_image(image_id) and self._display.set_active_mask_id(mask_id)

    def current_image_id_for_event(self) -> UUID | None:
        """Return the visible image only when it remains scope-authorized."""

        scope = self._scope
        if scope is None:
            self._log_rejection(CanvasRouteIdentity.empty(), None, "missing_scope")
            return None
        if not self._authorize(scope, scope.session.active_route, None):
            return None
        image_id = self._display.current_image_id()
        if image_id is None or image_id in scope.allowed_image_ids:
            return image_id
        self._log_rejection(
            scope.session.active_route, image_id, "foreign_current_image"
        )
        return None

    def _authorize(
        self,
        scope: InputRouteScope,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        mask_id: UUID | None = None,
    ) -> bool:
        """Return whether this scope can still mutate Input presentation."""

        authorization = self._session_boundary.authorize_display_mutation(
            scope.session.token(), canvas_kind=CanvasKind.INPUT
        )
        if authorization.accepted:
            return True
        reason = (
            authorization.rejection_reason
            or CanvasSessionRejectionReason.MISSING_SESSION
        )
        self._log_rejection(route, image_id, reason.value, mask_id)
        return False

    def _log_rejection(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        reason: str,
        mask_id: UUID | None = None,
    ) -> None:
        """Log one prompt-safe rejected route command."""

        scope = self._scope
        log_warning(
            _LOGGER,
            "Input document route command rejected",
            workflow_id=scope.session.workflow_id.value if scope is not None else "",
            canvas_kind=CanvasKind.INPUT.value,
            route_kind=route.route_kind,
            route_key=route.route_key,
            requested_image_id=image_id,
            requested_mask_id=mask_id or "",
            rejection_reason=reason,
        )


__all__ = ["InputRouteDisplayPort", "InputRouteProjector"]
