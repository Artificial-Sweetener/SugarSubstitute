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

"""Guard QPane display routes behind active canvas session authorization."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass, replace
from types import SimpleNamespace
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasKind,
    CanvasRouteIdentity,
    CanvasRouteSessionBoundaryPort,
    CanvasSessionRejectionReason,
    InputRouteScope,
    OutputCanvasHitValidation,
    OutputRouteScope,
)
from substitute.application.workflows.output_canvas_session import (
    deterministic_host_composition_id,
)
from substitute.presentation.canvas.qpane.input_pane_adapter import (
    InputQPaneRouteAdapter,
)
from substitute.presentation.canvas.qpane.output_pane_adapter import (
    OutputQPaneRouteAdapter,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.qpane.canvas_route_projector")


class InputRouteProjector:
    """Authorize Input QPane image routes against the active session."""

    def __init__(
        self,
        adapter: InputQPaneRouteAdapter,
        *,
        session_boundary: CanvasRouteSessionBoundaryPort,
    ) -> None:
        """Store the Input QPane adapter and shared session boundary."""

        self._adapter = adapter
        self._session_boundary = session_boundary
        self._scope: InputRouteScope | None = None

    def bind(self, scope: InputRouteScope) -> None:
        """Bind the current Input route scope."""

        self._scope = scope

    def show_image(self, image_id: UUID | None) -> bool:
        """Show image_id only when authorized by the active Input scope."""

        scope = self._scope
        if scope is None:
            self._log_rejection(
                route=CanvasRouteIdentity.empty(),
                image_id=image_id,
                reason="missing_scope",
            )
            return False
        if not self._authorize(
            scope, route=scope.session.active_route, image_id=image_id
        ):
            return False
        if image_id is not None and image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=scope.session.active_route,
                image_id=image_id,
                reason="foreign_image",
            )
            return False
        current_image_id = self._adapter.current_image_id()
        if current_image_id == image_id:
            return True
        return self._adapter.set_current_image_id(image_id)

    def show_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Show image_id and activate mask_id only when scope-authorized."""

        scope = self._scope
        if scope is None:
            self._log_rejection(
                route=CanvasRouteIdentity.empty(),
                image_id=image_id,
                mask_id=mask_id,
                reason="missing_scope",
            )
            return False
        if not self._authorize(
            scope,
            route=scope.session.active_route,
            image_id=image_id,
            mask_id=mask_id,
        ):
            return False
        if image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=scope.session.active_route,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_image",
            )
            return False
        if scope.allowed_mask_image_ids.get(mask_id) != image_id:
            self._log_rejection(
                route=scope.session.active_route,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_mask",
            )
            return False
        if not self.show_image(image_id):
            return False
        return self._adapter.set_active_mask_id(mask_id)

    def current_image_id_for_event(self) -> UUID | None:
        """Return the current image only when the active Input scope authorizes it."""

        scope = self._scope
        if scope is None:
            self._log_rejection(
                route=CanvasRouteIdentity.empty(),
                image_id=None,
                reason="missing_scope",
            )
            return None
        if not self._authorize(scope, route=scope.session.active_route, image_id=None):
            return None
        image_id = self._adapter.current_image_id()
        if image_id is None or image_id in scope.allowed_image_ids:
            return image_id
        self._log_rejection(
            route=scope.session.active_route,
            image_id=image_id,
            reason="foreign_current_image",
        )
        return None

    def loaded_image_id_for_event(self) -> UUID | None:
        """Return QPane's loaded image id after validating the active Input session."""

        scope = self._scope
        if scope is None:
            self._log_rejection(
                route=CanvasRouteIdentity.empty(),
                image_id=None,
                reason="missing_scope",
            )
            return None
        if not self._authorize(scope, route=scope.session.active_route, image_id=None):
            return None
        return self._adapter.current_image_id()

    def _authorize(
        self,
        scope: InputRouteScope,
        *,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        mask_id: UUID | None = None,
    ) -> bool:
        """Return whether the bound Input session token is still current."""

        authorization = self._session_boundary.authorize_display_mutation(
            scope.session.token(),
            canvas_kind=CanvasKind.INPUT,
        )
        if authorization.accepted:
            return True
        reason = (
            authorization.rejection_reason
            or CanvasSessionRejectionReason.MISSING_SESSION
        )
        self._log_rejection(
            route=route,
            image_id=image_id,
            mask_id=mask_id,
            reason=reason.value,
        )
        return False

    def _log_rejection(
        self,
        *,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        reason: str,
        mask_id: UUID | None = None,
    ) -> None:
        """Log one prompt-safe Input route rejection."""

        scope = self._scope
        log_warning(
            _LOGGER,
            "QPane route command rejected",
            workflow_id=scope.session.workflow_id.value if scope is not None else "",
            canvas_kind=CanvasKind.INPUT.value,
            route_kind=route.route_kind,
            route_key=route.route_key,
            requested_image_id=image_id,
            requested_mask_id=mask_id or "",
            requested_source_key="",
            requested_scene_key="",
            requested_composition_id="",
            rejection_reason=reason,
        )


class OutputRouteProjector:
    """Authorize Output QPane image, composition, comparison, and hit routes."""

    def __init__(
        self,
        adapter: OutputQPaneRouteAdapter,
        *,
        session_boundary: CanvasRouteSessionBoundaryPort,
    ) -> None:
        """Store the Output QPane adapter and shared session boundary."""

        self._adapter = adapter
        self._session_boundary = session_boundary
        self._scope: OutputRouteScope | None = None

    def bind(self, scope: OutputRouteScope) -> None:
        """Bind the current Output route scope."""

        self._scope = scope
        self._clear_foreign_active_composition(scope)

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Show image_id only when authorized by the active Output scope."""

        scope = self._scope
        if not self._authorize_current_scope(route=route, image_id=image_id):
            return False
        assert scope is not None
        if not self._route_may_activate(scope, route):
            self._log_route_rejection(route, reason="inactive_route_activation")
            return False
        if route.route_kind != "output_image":
            self._log_route_rejection(route, reason="route_kind_mismatch")
            return False
        if route.primary_image_id != image_id:
            self._log_rejection(
                route=route,
                image_id=image_id,
                reason="route_image_mismatch",
            )
            return False
        route_rejection_reason = self._route_rejection_reason(scope, route)
        if route_rejection_reason is not None:
            self._log_route_rejection(route, reason=route_rejection_reason)
            return False
        if image_id not in scope.allowed_image_ids:
            self._log_rejection(route=route, image_id=image_id, reason="foreign_image")
            return False
        if (
            self._adapter.current_image_id() == image_id
            and self._active_default_image_route_is(image_id)
        ):
            return True
        applied = self._activate_default_image_route(image_id)
        return applied

    def apply_source_grid_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Compose or replace a source-grid route only when authorized."""

        return self._apply_layered_route(
            route,
            request,
            activate=activate,
            route_kind="source_grid",
        )

    def apply_scene_overview_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Compose or replace a scene-overview route only when authorized."""

        return self._apply_layered_route(
            route,
            request,
            activate=activate,
            route_kind="scene_overview",
        )

    def clear_route(self, route: CanvasRouteIdentity) -> bool:
        """Clear the active Output route through the guarded route boundary."""

        if not self._authorize_current_scope(route=route, image_id=None):
            return False
        scope = self._scope
        assert scope is not None
        route_rejection_reason = self._route_rejection_reason(scope, route)
        if route_rejection_reason is not None:
            self._log_route_rejection(route, reason=route_rejection_reason)
            return False
        if (
            self._adapter.current_image_id() is None
            and self._adapter.current_composition_id() is None
        ):
            return True
        self._adapter.clear_comparison_image()
        applied = self._adapter.set_current_image_id(None)
        return applied

    def current_image_id_for_event(self) -> UUID | None:
        """Return the current image only when the active Output scope authorizes it."""

        route = self._active_route_or_empty()
        scope = self._scope
        if not self._authorize_current_scope(route=route, image_id=None):
            return None
        assert scope is not None
        image_id = self._adapter.current_image_id()
        if image_id is None or image_id in scope.allowed_image_ids:
            return image_id
        self._log_rejection(
            route=route,
            image_id=image_id,
            reason="foreign_current_image",
        )
        return None

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Return the deterministic composition ID for one host-owned route."""

        scope = self._scope
        workflow_id = scope.session.workflow_id.value if scope is not None else ""
        return deterministic_host_composition_id(
            canvas_kind=CanvasKind.OUTPUT,
            workflow_id=workflow_id,
            route=route,
        )

    def apply_compare(
        self,
        *,
        route: CanvasRouteIdentity,
        base_image_id: UUID,
        comparison_image_id: UUID,
        split_position: float,
        orientation: object,
    ) -> bool:
        """Apply comparison state only for two images inside the active scope."""

        scope = self._scope
        if not self._authorize_current_scope(route=route, image_id=base_image_id):
            return False
        assert scope is not None
        if not self._route_may_activate(scope, route):
            self._log_route_rejection(route, reason="inactive_route_activation")
            return False
        if not self._route_is_allowed(scope, route):
            self._log_route_rejection(route, reason="foreign_route")
            return False
        if base_image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=route,
                image_id=base_image_id,
                reason="foreign_compare_base",
            )
            return False
        if comparison_image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=route,
                image_id=comparison_image_id,
                reason="foreign_compare_image",
            )
            return False
        if not self.apply_final_image_route(route, base_image_id):
            return False
        if not self._active_default_image_route_is(
            base_image_id,
            require_snapshot=True,
        ):
            self._log_rejection(
                route=route,
                image_id=base_image_id,
                reason="compare_base_composition_invalid",
            )
            return False
        if not self._adapter.set_comparison_image_id(comparison_image_id):
            self._log_rejection(
                route=route,
                image_id=comparison_image_id,
                reason="compare_image_failed",
            )
            return False
        if not self._adapter.set_comparison_split(split_position, orientation):
            self._log_rejection(
                route=route,
                image_id=comparison_image_id,
                reason="compare_split_failed",
            )
            return False
        return True

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Clear comparison state for an authorized route."""

        if not self._authorize_current_scope(route=route, image_id=None):
            return False
        scope = self._scope
        assert scope is not None
        if not self._route_is_allowed(scope, route):
            self._log_route_rejection(route, reason="foreign_route")
            return False
        if not self._adapter.clear_comparison_image():
            self._log_rejection(
                route=route,
                image_id=None,
                reason="compare_clear_failed",
            )
            return False
        return True

    def validate_scene_hit(self, hit: object) -> OutputCanvasHitValidation:
        """Validate one public QPane scene hit against the active Output scope."""

        route = self._active_route_or_empty()
        if hit is None:
            self._log_rejection(route=route, image_id=None, reason="missing_hit")
            return OutputCanvasHitValidation.rejected("missing_hit")
        hit_image_id = _uuid_from_value(getattr(hit, "image_id", None))
        if not self._authorize_current_scope(route=route, image_id=hit_image_id):
            return OutputCanvasHitValidation.rejected("unauthorized_session")
        scope = self._scope
        assert scope is not None
        current_composition_id = self._adapter.current_composition_id()
        hit_composition_id = _uuid_from_value(getattr(hit, "composition_id", None))
        expected_composition_id = self.route_composition_id(route)
        composition_snapshot = self._adapter.composition_snapshot()
        composition_validation_unavailable = (
            current_composition_id is None
            and hit_composition_id is None
            and composition_snapshot is None
        )
        if not composition_validation_unavailable and (
            current_composition_id is None
            or hit_composition_id != current_composition_id
        ):
            self._log_rejection(
                route=route,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
                reason="hit_composition_mismatch",
            )
            return OutputCanvasHitValidation.rejected("hit_composition_mismatch")
        if (
            not composition_validation_unavailable
            and hit_composition_id != expected_composition_id
        ):
            self._log_rejection(
                route=route,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
                reason="foreign_hit_composition",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_composition")
        if not self._active_composition_is_valid(expected_composition_id):
            self._log_rejection(
                route=route,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
                reason="composition_snapshot_invalid",
            )
            return OutputCanvasHitValidation.rejected("composition_snapshot_invalid")
        if hit_image_id is not None and hit_image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=route,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
                reason="foreign_hit_image",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_image")
        metadata = getattr(hit, "metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        role = getattr(hit, "role", None)
        if role == "scene-output":
            return self._validate_scene_overview_hit(
                route=route,
                metadata=metadata,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
            )
        if role == "final-output":
            return self._validate_final_output_hit(
                route=route,
                metadata=metadata,
                image_id=hit_image_id,
                composition_id=hit_composition_id,
            )
        self._log_rejection(
            route=route,
            image_id=hit_image_id,
            composition_id=hit_composition_id,
            reason="unsupported_hit_role",
        )
        return OutputCanvasHitValidation.rejected("unsupported_hit_role")

    def hit_test_scene(self, point: object) -> OutputCanvasHitValidation:
        """Hit-test QPane scene content and validate the returned hit."""

        return self.validate_scene_hit(self._adapter.scene_hit_test(point))

    def _validate_scene_overview_hit(
        self,
        *,
        route: CanvasRouteIdentity,
        metadata: Mapping[str, object],
        image_id: UUID | None,
        composition_id: UUID | None,
    ) -> OutputCanvasHitValidation:
        """Validate one scene-overview hit."""

        scope = self._scope
        assert scope is not None
        if route.route_kind != "scene_overview":
            self._log_rejection(
                route=route,
                image_id=image_id,
                composition_id=composition_id,
                reason="scene_hit_outside_overview",
            )
            return OutputCanvasHitValidation.rejected("scene_hit_outside_overview")
        scene_key = metadata.get("scene_key")
        if not isinstance(scene_key, str) or scene_key not in scope.allowed_scene_keys:
            self._log_rejection(
                route=route,
                image_id=image_id,
                scene_key=scene_key if isinstance(scene_key, str) else None,
                composition_id=composition_id,
                reason="foreign_hit_scene",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_scene")
        return OutputCanvasHitValidation.scene(scene_key=scene_key, image_id=image_id)

    def _validate_final_output_hit(
        self,
        *,
        route: CanvasRouteIdentity,
        metadata: Mapping[str, object],
        image_id: UUID | None,
        composition_id: UUID | None,
    ) -> OutputCanvasHitValidation:
        """Validate one final-output hit."""

        scope = self._scope
        assert scope is not None
        source_key = metadata.get("source_key")
        if (
            not isinstance(source_key, str)
            or source_key not in scope.allowed_source_keys
        ):
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key if isinstance(source_key, str) else None,
                composition_id=composition_id,
                reason="foreign_hit_source",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_source")
        route_source_key, route_scene_key = _route_source_and_scene(route)
        if route_source_key is not None and route_source_key != source_key:
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key,
                composition_id=composition_id,
                reason="hit_source_mismatch",
            )
            return OutputCanvasHitValidation.rejected("hit_source_mismatch")
        set_index = _set_index_from_value(metadata.get("set_index"))
        if set_index is None:
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key,
                composition_id=composition_id,
                reason="missing_hit_set",
            )
            return OutputCanvasHitValidation.rejected("missing_hit_set")
        if image_id is None:
            image_id = _uuid_from_value(metadata.get("image_id"))
        if image_id is None or image_id not in scope.allowed_image_ids:
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key,
                composition_id=composition_id,
                reason="foreign_hit_image",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_image")
        scene_key = metadata.get("scene_key")
        if (
            isinstance(scene_key, str)
            and scene_key
            and scene_key not in scope.allowed_scene_keys
        ):
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key,
                scene_key=scene_key,
                composition_id=composition_id,
                reason="foreign_hit_scene",
            )
            return OutputCanvasHitValidation.rejected("foreign_hit_scene")
        if (
            route_scene_key is not None
            and route_scene_key
            and isinstance(scene_key, str)
            and scene_key
            and route_scene_key != scene_key
        ):
            self._log_rejection(
                route=route,
                image_id=image_id,
                source_key=source_key,
                scene_key=scene_key,
                composition_id=composition_id,
                reason="hit_scene_mismatch",
            )
            return OutputCanvasHitValidation.rejected("hit_scene_mismatch")
        return OutputCanvasHitValidation.final_output(
            image_id=image_id,
            source_key=source_key,
            set_index=set_index,
            scene_key=scene_key if isinstance(scene_key, str) and scene_key else None,
        )

    def _authorize_current_scope(
        self,
        *,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
    ) -> bool:
        """Return whether the bound Output session token is still current."""

        scope = self._scope
        if scope is None:
            self._log_rejection(route=route, image_id=image_id, reason="missing_scope")
            return False
        authorization = self._session_boundary.authorize_display_mutation(
            scope.session.token(),
            canvas_kind=CanvasKind.OUTPUT,
        )
        if authorization.accepted:
            return True
        reason = (
            authorization.rejection_reason
            or CanvasSessionRejectionReason.MISSING_SESSION
        )
        self._log_rejection(route=route, image_id=image_id, reason=reason.value)
        return False

    def _apply_layered_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
        route_kind: str,
    ) -> bool:
        """Compose or replace one layered Output route after scope validation."""

        scope = self._scope
        if not self._authorize_current_scope(route=route, image_id=None):
            return False
        assert scope is not None
        if route.route_kind != route_kind:
            self._log_route_rejection(route, reason="route_kind_mismatch")
            return False
        route_rejection_reason = self._route_rejection_reason(scope, route)
        if route_rejection_reason is not None:
            self._log_route_rejection(route, reason=route_rejection_reason)
            return False
        if activate and not self._route_may_activate(scope, route):
            self._log_route_rejection(route, reason="inactive_route_activation")
            return False
        composition_id = self.route_composition_id(route)
        if composition_id not in scope.allowed_composition_ids:
            self._log_rejection(
                route=route,
                image_id=None,
                composition_id=composition_id,
                reason="foreign_composition_id",
            )
            return False
        layer_image_ids = tuple(_layer_image_ids(request))
        foreign_images = [
            image_id
            for image_id in layer_image_ids
            if image_id not in scope.allowed_image_ids
        ]
        if foreign_images:
            self._log_rejection(
                route=route,
                image_id=foreign_images[0],
                composition_id=composition_id,
                reason="foreign_scene_layer",
            )
            return False
        if not layer_image_ids:
            self._log_rejection(
                route=route,
                image_id=None,
                composition_id=composition_id,
                reason="empty_scene_layers",
            )
            return False
        route_request = _request_with_composition_id(request, composition_id)
        composed_id = self._adapter.compose_scene(route_request, activate=activate)
        if composed_id != composition_id:
            self._log_rejection(
                route=route,
                image_id=None,
                composition_id=composition_id,
                reason="composition_failed",
            )
            return False
        if activate and not self._active_composition_is_valid(composition_id):
            self._log_rejection(
                route=route,
                image_id=None,
                composition_id=composition_id,
                reason="active_composition_invalid",
            )
            return False
        return True

    def _route_rejection_reason(
        self,
        scope: OutputRouteScope,
        route: CanvasRouteIdentity,
    ) -> str | None:
        """Return the rejection reason for one route identity, if any."""

        source_key, scene_key = _route_source_and_scene(route)
        if source_key is not None and source_key not in scope.allowed_source_keys:
            return "foreign_source_route"
        if (
            scene_key is not None
            and scene_key
            and scene_key not in scope.allowed_scene_keys
        ):
            return "foreign_scene_route"
        return None

    def _route_is_allowed(
        self,
        scope: OutputRouteScope,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether route source and scene identities fit the active scope."""

        return self._route_rejection_reason(scope, route) is None

    def _route_may_activate(
        self,
        scope: OutputRouteScope,
        route: CanvasRouteIdentity,
    ) -> bool:
        """Return whether route can become visible for the current session."""

        if route == scope.session.active_route:
            return True
        if route.route_kind != "output_image" or route.primary_image_id is None:
            return False
        return (
            route.primary_image_id in scope.allowed_image_ids
            and route.primary_image_id not in scope.session.allowed_image_ids
        )

    def _clear_foreign_active_composition(self, scope: OutputRouteScope) -> None:
        """Clear active QPane composition state that is foreign to a new scope."""

        current_composition_id = self._adapter.current_composition_id()
        snapshot = self._adapter.composition_snapshot()
        if current_composition_id is None:
            current_image_id = self._adapter.current_image_id()
            if (
                current_image_id is not None
                and current_image_id not in scope.allowed_image_ids
            ):
                self._log_rejection(
                    route=scope.session.active_route,
                    image_id=current_image_id,
                    reason="foreign_active_image",
                )
                self._adapter.clear_comparison_image()
                self._adapter.set_current_image_id(None)
            return
        compositions = getattr(snapshot, "compositions", None)
        entry = (
            compositions.get(current_composition_id)
            if isinstance(compositions, Mapping) and current_composition_id is not None
            else None
        )
        if current_composition_id is None or entry is None:
            self._adapter.clear_comparison_image()
            self._adapter.set_current_image_id(None)
            return
        if self._composition_entry_is_valid(entry, scope):
            return
        self._log_rejection(
            route=scope.session.active_route,
            image_id=_uuid_from_value(getattr(entry, "current_image_id", None)),
            composition_id=current_composition_id,
            reason="foreign_active_composition",
        )
        self._adapter.clear_comparison_image()
        if getattr(entry, "kind", None) != "default-image":
            self._adapter.remove_composition(current_composition_id)
        self._adapter.set_current_image_id(None)

    def _composition_is_valid(self, composition_id: UUID) -> bool:
        """Validate one QPane composition snapshot against the active scope."""

        scope = self._scope
        if scope is None:
            return False
        snapshot = self._adapter.composition_snapshot()
        if snapshot is None:
            return False
        compositions = getattr(snapshot, "compositions", None)
        if not isinstance(compositions, Mapping):
            return False
        entry = compositions.get(composition_id)
        if entry is None:
            return False
        return self._composition_entry_is_valid(entry, scope)

    def _composition_entry_is_valid(
        self,
        entry: object,
        scope: OutputRouteScope,
    ) -> bool:
        """Return whether one QPane composition entry fits the active scope."""

        source_image_ids = getattr(entry, "source_image_ids", ())
        if not isinstance(source_image_ids, Iterable):
            return False
        if any(
            not isinstance(image_id, UUID) or image_id not in scope.allowed_image_ids
            for image_id in source_image_ids
        ):
            return False
        current_image_id = getattr(entry, "current_image_id", None)
        if current_image_id is not None and (
            not isinstance(current_image_id, UUID)
            or current_image_id not in scope.allowed_image_ids
        ):
            return False
        comparison = getattr(entry, "comparison", None)
        comparison_enabled = bool(getattr(comparison, "enabled", False))
        comparison_source_id = getattr(comparison, "source_id", None)
        comparison_source_kind = getattr(comparison, "source_kind", None)
        if (
            comparison_enabled
            and (
                comparison_source_kind == "catalog"
                or isinstance(comparison_source_id, UUID)
            )
            and comparison_source_id not in scope.allowed_image_ids
        ):
            return False
        return True

    def _active_composition_is_valid(self, composition_id: UUID) -> bool:
        """Validate the active composition ID and snapshot against the active scope."""

        current_composition_id = self._adapter.current_composition_id()
        snapshot = self._adapter.composition_snapshot()
        if current_composition_id is None and snapshot is None:
            return False
        snapshot_current_id = (
            getattr(snapshot, "current_composition_id", None)
            if snapshot is not None
            else None
        )
        return (
            current_composition_id == composition_id
            and snapshot_current_id == composition_id
            and self._composition_is_valid(composition_id)
        )

    def _active_default_image_route_is(
        self,
        image_id: UUID,
        *,
        require_snapshot: bool = False,
    ) -> bool:
        """Return whether QPane is actively rendering image_id's default route."""

        current_composition_id = self._adapter.current_composition_id()
        snapshot = self._adapter.composition_snapshot()
        if current_composition_id is None or snapshot is None:
            return not require_snapshot
        if getattr(snapshot, "current_composition_id", None) != current_composition_id:
            return False
        compositions = getattr(snapshot, "compositions", None)
        if not isinstance(compositions, Mapping):
            return False
        entry = compositions.get(current_composition_id)
        return (
            entry is not None
            and getattr(entry, "kind", None) == "default-image"
            and getattr(entry, "current_image_id", None) == image_id
        )

    def _activate_default_image_route(
        self,
        image_id: UUID,
    ) -> bool:
        """Select one image and open its QPane default-image composition."""

        return self._adapter.activate_default_image_id(
            image_id
        ) and self._active_default_image_route_is(image_id)

    def _active_route_or_empty(self) -> CanvasRouteIdentity:
        """Return the bound session route, or the empty route."""

        scope = self._scope
        return (
            CanvasRouteIdentity.empty() if scope is None else scope.session.active_route
        )

    def _log_route_rejection(self, route: CanvasRouteIdentity, *, reason: str) -> None:
        """Log one route-level rejection with parsed source/scene context."""

        source_key, scene_key = _route_source_and_scene(route)
        self._log_rejection(
            route=route,
            image_id=route.primary_image_id,
            source_key=source_key,
            scene_key=scene_key,
            reason=reason,
        )

    def _log_rejection(
        self,
        *,
        route: CanvasRouteIdentity,
        image_id: UUID | None,
        reason: str,
        source_key: str | None = None,
        scene_key: str | None = None,
        composition_id: UUID | None = None,
    ) -> None:
        """Log one prompt-safe Output route rejection."""

        scope = self._scope
        route_source_key, route_scene_key = _route_source_and_scene(route)
        log_warning(
            _LOGGER,
            "QPane route command rejected",
            workflow_id=scope.session.workflow_id.value if scope is not None else "",
            canvas_kind=CanvasKind.OUTPUT.value,
            route_kind=route.route_kind,
            route_key=route.route_key,
            requested_image_id=image_id,
            requested_source_key=source_key
            if source_key is not None
            else route_source_key or "",
            requested_scene_key=scene_key
            if scene_key is not None
            else route_scene_key or "",
            requested_composition_id=composition_id or "",
            rejection_reason=reason,
        )


def _request_with_composition_id(request: object, composition_id: UUID) -> object:
    """Return request with a deterministic composition ID."""

    if is_dataclass(request) and not isinstance(request, type):
        return replace(request, composition_id=composition_id)
    if isinstance(request, SimpleNamespace):
        values = vars(request).copy()
        values["composition_id"] = composition_id
        return SimpleNamespace(**values)
    request_type = type(request)
    field_names = (
        {field.name for field in fields(request)} if is_dataclass(request) else set()
    )
    if field_names:
        values = {name: getattr(request, name) for name in field_names}
        values["composition_id"] = composition_id
        return request_type(**values)
    raise TypeError("Scene route request must be a dataclass or SimpleNamespace.")


def _layer_image_ids(request: object) -> Iterable[UUID]:
    """Yield UUID image IDs from one scene request."""

    layers = getattr(request, "layers", ())
    if not isinstance(layers, Iterable):
        return ()
    return (
        image_id
        for image_id in (getattr(layer, "image_id", None) for layer in layers)
        if isinstance(image_id, UUID)
    )


def _route_source_and_scene(
    route: CanvasRouteIdentity,
) -> tuple[str | None, str | None]:
    """Return source and scene identities encoded in one route key."""

    source_key: str | None = None
    scene_key: str | None = None
    for segment in route.route_key.split(";"):
        if segment.startswith("source:"):
            source_key = segment.removeprefix("source:")
        elif segment.startswith("scene:"):
            scene_key = segment.removeprefix("scene:")
    return source_key, scene_key


def _uuid_from_value(value: object) -> UUID | None:
    """Return a UUID from QPane hit values or serialized metadata."""

    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _set_index_from_value(value: object) -> int | None:
    """Return a positive set index from hit metadata."""

    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str):
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


__all__ = [
    "InputRouteProjector",
    "OutputRouteProjector",
    "deterministic_host_composition_id",
]
