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

"""Own authorized Input route scope and active image or mask projection."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
    InputRouteScope,
)
from substitute.application.workflows.input_mask_layer_removal import (
    mask_belongs_to_image,
    workflow_owns_input_image,
)
from substitute.domain.workflow import CanvasKind, CanvasRouteIdentity, WorkflowState
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.input_route_projection_service")


class InputRouteProjectionService:
    """Authorize and project workflow-owned Input routes."""

    def __init__(
        self,
        *,
        projector: InputRouteProjectorPort,
        session_boundary: CanvasRouteSessionBoundaryPort,
    ) -> None:
        """Store the route projector and shared session boundary."""

        self._projector = projector
        self._session_boundary = session_boundary

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        """Project the active workflow's authorized Input image and mask route."""

        workflow = workflows.get(active_workflow_id)
        if workflow is None:
            self.bind_scope(active_workflow_id, None)
            self._projector.show_image(None)
            return
        image_id = self._valid_active_image(workflow)
        active_mask_id = self._valid_active_mask(workflow)
        self.bind_scope(
            active_workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if image_id is None:
            self._projector.show_image(None)
        elif active_mask_id is not None:
            self._projector.show_mask(image_id, active_mask_id)
        else:
            self._projector.show_image(image_id)

    def set_active_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Persist and display an Input image owned by the workflow."""

        if not workflow_owns_input_image(workflow, image_id):
            log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=None,
                reason="foreign_input_image",
            )
            return False
        workflow.canvas.input_image_uuid = image_id
        active_mask_id = self._valid_active_mask(workflow)
        self.bind_scope(workflow_id, workflow, active_mask_id=active_mask_id)
        if active_mask_id is not None:
            return self._projector.show_mask(image_id, active_mask_id)
        return self._projector.show_image(image_id)

    def set_active_mask(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Persist and display a mask owned by the active Input image."""

        image_id = workflow.canvas.input_image_uuid
        if image_id is None:
            log_input_rejection(
                workflow_id=workflow_id,
                image_id=None,
                mask_id=mask_id,
                reason="missing_active_input_image",
            )
            return False
        if not mask_belongs_to_image(workflow, mask_id, image_id):
            log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_input_mask",
            )
            return False
        workflow.canvas.active_input_mask_uuid = mask_id
        self.bind_scope(workflow_id, workflow, active_mask_id=mask_id)
        return self._projector.show_mask(image_id, mask_id)

    def bind_scope(
        self,
        workflow_id: str,
        workflow: WorkflowState | None,
        *,
        active_mask_id: UUID | None = None,
    ) -> None:
        """Bind the authorized Input route scope for one workflow."""

        input_image_id = None if workflow is None else workflow.canvas.input_image_uuid
        session = self._session_boundary.bind_input_session(
            workflow_id=workflow_id,
            active_route=_route_identity(input_image_id, active_mask_id),
        )
        self._projector.bind(
            InputRouteScope(
                session=session,
                allowed_image_ids=_allowed_image_ids(workflow),
                allowed_mask_image_ids=_allowed_mask_image_ids(workflow),
            )
        )

    def bind_scope_for_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> None:
        """Bind an authorized scope for one explicit owned image operation."""

        session = self._session_boundary.bind_input_session(
            workflow_id=workflow_id,
            active_route=_route_identity(image_id, None),
        )
        allowed_image_ids = set(_allowed_image_ids(workflow))
        allowed_image_ids.add(image_id)
        self._projector.bind(
            InputRouteScope(
                session=session,
                allowed_image_ids=frozenset(allowed_image_ids),
                allowed_mask_image_ids=_allowed_mask_image_ids(workflow),
            )
        )

    def show_image(self, image_id: UUID | None) -> bool:
        """Show one image through the currently bound authorized scope."""

        return self._projector.show_image(image_id)

    def show_mask(self, image_id: UUID, mask_id: UUID) -> bool:
        """Show one mask through the currently bound authorized scope."""

        return self._projector.show_mask(image_id, mask_id)

    @staticmethod
    def _valid_active_mask(workflow: WorkflowState) -> UUID | None:
        """Return the active mask only when it belongs to the active image."""

        mask_id = workflow.canvas.active_input_mask_uuid
        if mask_id is None:
            return None
        image_id = workflow.canvas.mask_image_owners().get(mask_id)
        if image_id is None or workflow.canvas.input_image_uuid is None:
            workflow.canvas.active_input_mask_uuid = None
            return None
        if image_id != workflow.canvas.input_image_uuid:
            workflow.canvas.active_input_mask_uuid = None
            return None
        return mask_id

    @staticmethod
    def _valid_active_image(workflow: WorkflowState) -> UUID | None:
        """Return the active image only when workflow keyed state owns it."""

        image_id = workflow.canvas.input_image_uuid
        if image_id is None:
            return None
        if workflow.canvas.image_entry_for_id(image_id) is not None:
            return image_id
        workflow.canvas.input_image_uuid = None
        workflow.canvas.active_input_mask_uuid = None
        return None


def _allowed_image_ids(workflow: WorkflowState | None) -> frozenset[UUID]:
    """Return workflow-owned Input image IDs allowed for display routes."""

    return frozenset() if workflow is None else frozenset(workflow.canvas.image_ids())


def _allowed_mask_image_ids(workflow: WorkflowState | None) -> Mapping[UUID, UUID]:
    """Return workflow mask ownership used to authorize mask activation."""

    return {} if workflow is None else workflow.canvas.mask_image_owners()


def _route_identity(
    image_id: UUID | None,
    mask_id: UUID | None,
) -> CanvasRouteIdentity:
    """Return the active Input route identity without renderer policy."""

    if image_id is None:
        return CanvasRouteIdentity.empty()
    suffix = f"image:{image_id}"
    if mask_id is not None:
        suffix = f"{suffix};mask:{mask_id}"
    return CanvasRouteIdentity(
        route_kind="input_image",
        route_key=suffix,
        primary_image_id=image_id,
    )


def log_input_rejection(
    *,
    workflow_id: str,
    image_id: UUID | None,
    mask_id: UUID | None,
    reason: str,
) -> None:
    """Log one prompt-safe Input state or route authorization rejection."""

    log_warning(
        _LOGGER,
        "Input canvas route command rejected",
        workflow_id=workflow_id,
        canvas_kind=CanvasKind.INPUT.value,
        requested_image_id=image_id,
        requested_mask_id=mask_id,
        rejection_reason=reason,
    )


__all__ = ["InputRouteProjectionService", "log_input_rejection"]
