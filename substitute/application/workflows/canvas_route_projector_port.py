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

"""Define application-facing ports for guarded canvas route projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.domain.workflow import (
    CanvasGenerationIdentity,
    CanvasBoundSession,
    CanvasKind,
    CanvasMutationAuthorization,
    CanvasRouteIdentity,
    CanvasSessionBoundary,
    CanvasSessionRejectionReason,
    CanvasSessionToken,
    InputCanvasSession,
    OutputCanvasSession as OutputCanvasRouteSession,
)


class OutputCanvasHitKind(StrEnum):
    """Describe accepted QPane scene-hit intent kinds."""

    FINAL_OUTPUT = "final_output"
    SCENE = "scene"


@dataclass(frozen=True, slots=True)
class InputRouteScope:
    """Describe the active Input projection that may mutate QPane display."""

    session: InputCanvasSession
    allowed_image_ids: frozenset[UUID]
    allowed_mask_image_ids: Mapping[UUID, UUID] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OutputRouteScope:
    """Describe the active Output projection that may mutate QPane display."""

    session: OutputCanvasSession
    allowed_image_ids: frozenset[UUID]
    allowed_source_keys: frozenset[str]
    allowed_scene_keys: frozenset[str]
    allowed_composition_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class OutputCanvasHitValidation:
    """Return validated scene-hit intent or a prompt-safe rejection reason."""

    accepted: bool
    kind: OutputCanvasHitKind | None = None
    image_id: UUID | None = None
    source_key: str | None = None
    scene_key: str | None = None
    set_index: int | None = None
    rejection_reason: str | None = None

    @classmethod
    def rejected(cls, reason: str) -> "OutputCanvasHitValidation":
        """Return a rejected scene-hit validation result."""

        return cls(accepted=False, rejection_reason=reason)

    @classmethod
    def final_output(
        cls,
        *,
        image_id: UUID,
        source_key: str,
        set_index: int,
        scene_key: str | None,
    ) -> "OutputCanvasHitValidation":
        """Return an accepted final-output hit validation result."""

        return cls(
            accepted=True,
            kind=OutputCanvasHitKind.FINAL_OUTPUT,
            image_id=image_id,
            source_key=source_key,
            scene_key=scene_key,
            set_index=set_index,
        )

    @classmethod
    def scene(
        cls,
        *,
        scene_key: str,
        image_id: UUID | None = None,
    ) -> "OutputCanvasHitValidation":
        """Return an accepted scene-overview hit validation result."""

        return cls(
            accepted=True,
            kind=OutputCanvasHitKind.SCENE,
            image_id=image_id,
            scene_key=scene_key,
        )


class InputRouteProjectorPort(Protocol):
    """Apply authorized Input image routes to QPane display state."""

    def bind(self, scope: InputRouteScope) -> None:
        """Bind the current Input route scope."""

    def show_image(self, image_id: UUID | None) -> bool:
        """Show image_id when authorized by the active Input scope."""

    def show_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Show an Input image and activate one authorized mask layer."""

    def current_image_id_for_event(self) -> UUID | None:
        """Return the current Input image only when it is scope-authorized."""

    def loaded_image_id_for_event(self) -> UUID | None:
        """Return a QPane-loaded image id after session authorization only."""


class OutputRouteProjectorPort(Protocol):
    """Apply authorized Output routes to QPane display state."""

    def bind(self, scope: OutputRouteScope) -> None:
        """Bind the current Output route scope."""

    def apply_final_image_route(
        self,
        route: CanvasRouteIdentity,
        image_id: UUID,
    ) -> bool:
        """Show one concrete Output image when authorized by the active scope."""

    def apply_source_grid_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Compose or replace one source-grid route when authorized."""

    def apply_scene_overview_route(
        self,
        route: CanvasRouteIdentity,
        request: object,
        *,
        activate: bool,
    ) -> bool:
        """Compose or replace one scene-overview route when authorized."""

    def clear_route(self, route: CanvasRouteIdentity) -> bool:
        """Clear the active Output route when authorized."""

    def current_image_id_for_event(self) -> UUID | None:
        """Return the current Output image only when it is scope-authorized."""

    def route_composition_id(self, route: CanvasRouteIdentity) -> UUID:
        """Return the deterministic composition ID for one host-owned route."""

    def apply_compare(
        self,
        *,
        route: CanvasRouteIdentity,
        base_image_id: UUID,
        comparison_image_id: UUID,
        split_position: float,
        orientation: object,
    ) -> bool:
        """Apply comparison state after validating both image identities."""

    def clear_compare(self, *, route: CanvasRouteIdentity) -> bool:
        """Clear comparison state for an authorized route."""

    def validate_scene_hit(self, hit: object) -> OutputCanvasHitValidation:
        """Validate one public QPane scene hit against the active scope."""

    def hit_test_scene(self, point: object) -> OutputCanvasHitValidation:
        """Hit-test QPane scene content and validate the result."""


class CanvasRouteSessionBoundaryPort(Protocol):
    """Own shared route-session identity for QPane display projectors."""

    def bind_input_session(
        self,
        *,
        workflow_id: str,
        active_route: CanvasRouteIdentity,
    ) -> InputCanvasSession:
        """Bind the active Input route session."""

    def bind_output_session(
        self,
        *,
        workflow_id: str,
        active_route: CanvasRouteIdentity,
        generation_identity: CanvasGenerationIdentity | None = None,
    ) -> OutputCanvasRouteSession:
        """Bind the active Output route session."""

    def current_session(self, canvas_kind: CanvasKind) -> CanvasBoundSession | None:
        """Return the current session for one canvas kind."""

    def adopt_session(self, session: CanvasBoundSession) -> bool:
        """Adopt a current-or-newer externally minted canvas session."""

    def authorize_display_mutation(
        self,
        token: CanvasSessionToken,
        *,
        canvas_kind: CanvasKind | None = None,
        active_route: CanvasRouteIdentity | None = None,
    ) -> CanvasMutationAuthorization:
        """Return whether token may mutate display state."""


def create_canvas_session_boundary() -> CanvasRouteSessionBoundaryPort:
    """Create the application-owned shared route-session boundary."""

    return CanvasSessionBoundary()


__all__ = [
    "CanvasKind",
    "CanvasRouteIdentity",
    "CanvasRouteSessionBoundaryPort",
    "CanvasSessionRejectionReason",
    "create_canvas_session_boundary",
    "InputRouteProjectorPort",
    "InputRouteScope",
    "OutputCanvasHitKind",
    "OutputCanvasHitValidation",
    "OutputRouteProjectorPort",
    "OutputRouteScope",
]
