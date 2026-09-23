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

"""Own Input mask creation, replacement, association, and removal."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_canvas_ports import (
    MaskLayerRemovalAuthorization,
    MaskLayerRemovalOutcome,
)
from substitute.application.workflows.input_mask_layer_removal import (
    authorize_workflow_mask_layer_removal,
    commit_workflow_mask_layer_removal,
    mask_belongs_to_image,
    workflow_owns_input_image,
)
from substitute.application.workflows.input_mask_visual_state_service import (
    InputMaskVisualStateService,
)
from substitute.application.workflows.input_route_projection_service import (
    InputRouteProjectionService,
    log_input_rejection,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_error

_LOGGER = get_logger("application.workflows.input_mask_asset_service")


class InputMaskAssetService:
    """Own workflow-associated live Input mask layer lifecycle."""

    def __init__(
        self,
        *,
        document: InputCanvasDocumentPort,
        routes: InputRouteProjectionService,
        visuals: InputMaskVisualStateService,
    ) -> None:
        """Store document, route, and visual-state collaborators."""

        self._document = document
        self._routes = routes
        self._visuals = visuals

    def create_for_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        size: object,
    ) -> UUID | None:
        """Create one blank mask layer for an explicitly owned Input image."""

        if not self._prepare_image(
            workflow_id,
            workflow,
            image_id,
            rejection_reason="foreign_mask_create_image",
        ):
            return None
        mask_id = self._document.create_blank_mask(image_id, size)
        if mask_id is None:
            log_error(
                _LOGGER,
                "Input canvas mask layer creation failed",
                workflow_id=workflow_id,
                association_key=association_key,
                image_id=str(image_id),
                size=str(size),
                failure_reason="blank_mask_creation_returned_none",
            )
            return None
        workflow.canvas.bind_mask(association_key, mask_id, image_id)
        self._visuals.apply_materialized_opacity(
            workflow_id,
            workflow,
            association_key,
            mask_id,
        )
        log_debug(
            _LOGGER,
            "Created input canvas mask layer for image",
            workflow_id=workflow_id,
            association_key=association_key,
            image_id=str(image_id),
            mask_id=str(mask_id),
        )
        return mask_id

    def load_from_file(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        path: Path,
    ) -> UUID | None:
        """Load one mask file layer for an explicitly owned Input image."""

        if not self._prepare_image(
            workflow_id,
            workflow,
            image_id,
            rejection_reason="foreign_mask_load_image",
        ):
            return None
        mask_id = self._document.load_mask_from_file(image_id, path)
        if mask_id is None:
            log_error(
                _LOGGER,
                "Input canvas mask file load failed",
                workflow_id=workflow_id,
                association_key=association_key,
                image_id=str(image_id),
                path=str(path),
                failure_reason="mask_file_load_returned_none",
            )
            return None
        workflow.canvas.bind_mask(association_key, mask_id, image_id)
        self._visuals.apply_materialized_opacity(
            workflow_id,
            workflow,
            association_key,
            mask_id,
        )
        log_debug(
            _LOGGER,
            "Loaded input canvas mask layer from file",
            workflow_id=workflow_id,
            association_key=association_key,
            image_id=str(image_id),
            mask_id=str(mask_id),
            path=str(path),
        )
        return mask_id

    def update_from_file(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        mask_id: UUID,
        path: Path,
        image_dimensions: tuple[int, int] | None,
        mask_dimensions: tuple[int, int] | None,
    ) -> bool:
        """Update one associated mask layer after ownership validation."""

        if not workflow_owns_input_image(workflow, image_id):
            return _reject(workflow_id, image_id, mask_id, "foreign_mask_update_image")
        mask_entry = workflow.canvas.mask_entry(association_key)
        collection = workflow.canvas.regional_mask_collection(association_key)
        association_matches = (
            mask_entry is not None and mask_entry.mask_id == mask_id
        ) or (collection is not None and collection.entry_for_mask(mask_id) is not None)
        if not association_matches:
            return _reject(
                workflow_id,
                image_id,
                mask_id,
                "mask_update_association_mismatch",
            )
        if not mask_belongs_to_image(workflow, mask_id, image_id):
            return _reject(workflow_id, image_id, mask_id, "foreign_mask_update_mask")
        if image_dimensions is None or mask_dimensions is None:
            return _reject(
                workflow_id,
                image_id,
                mask_id,
                "mask_update_unverified_dimensions",
            )
        if image_dimensions != mask_dimensions:
            return _reject(
                workflow_id,
                image_id,
                mask_id,
                "mask_update_dimensions_mismatch",
            )
        self._routes.bind_scope_for_image(workflow_id, workflow, image_id)
        if not self._routes.show_image(image_id):
            return False
        updated = self._document.replace_mask_from_file(mask_id, path)
        log_debug(
            _LOGGER,
            "Updated input canvas mask layer from file",
            workflow_id=workflow_id,
            association_key=association_key,
            image_id=str(image_id),
            mask_id=str(mask_id),
            path=str(path),
            updated=updated,
        )
        return updated

    @staticmethod
    def authorize_removal(
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
        mask_id: UUID,
    ) -> MaskLayerRemovalAuthorization | None:
        """Authorize one owned live-layer side effect before durable mutation."""

        return authorize_workflow_mask_layer_removal(
            workflow_id=workflow_id,
            workflow=workflow,
            image_id=image_id,
            mask_id=mask_id,
        )

    def commit_removal(
        self,
        authorization: MaskLayerRemovalAuthorization,
    ) -> MaskLayerRemovalOutcome:
        """Apply one previously authorized live-layer removal side effect."""

        return commit_workflow_mask_layer_removal(
            input_document=self._document,
            authorization=authorization,
        )

    def drop_association(
        self,
        workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Remove one stale mask association and detach its layer if unused."""

        entry = workflow.canvas.remove_mask_entry(association_key)
        if entry is None:
            return
        if workflow.canvas.mask_entry_for_id(entry.mask_id) is not None:
            log_debug(
                _LOGGER,
                "Dropped shared input canvas mask association",
                association_key=association_key,
                image_id=str(entry.image_id),
                mask_id=str(entry.mask_id),
                pane_removed=False,
            )
            return
        if workflow.canvas.active_input_mask_uuid == entry.mask_id:
            workflow.canvas.active_input_mask_uuid = None
        removed = self._document.remove_mask_from_image(entry.image_id, entry.mask_id)
        log_debug(
            _LOGGER,
            "Dropped input canvas mask association",
            association_key=association_key,
            image_id=str(entry.image_id),
            mask_id=str(entry.mask_id),
            pane_removed=removed,
        )

    def _prepare_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
        *,
        rejection_reason: str,
    ) -> bool:
        """Authorize and project one explicit image for mask mutation."""

        if not workflow_owns_input_image(workflow, image_id):
            return _reject(workflow_id, image_id, None, rejection_reason)
        self._routes.bind_scope_for_image(workflow_id, workflow, image_id)
        return self._routes.show_image(image_id)


def _reject(
    workflow_id: str,
    image_id: UUID,
    mask_id: UUID | None,
    reason: str,
) -> bool:
    """Log one rejected mask mutation and return false."""

    log_input_rejection(
        workflow_id=workflow_id,
        image_id=image_id,
        mask_id=mask_id,
        reason=reason,
    )
    return False


__all__ = ["InputMaskAssetService"]
