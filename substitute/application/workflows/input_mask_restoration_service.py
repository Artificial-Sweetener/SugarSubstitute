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

"""Restore archived Input masks into live document layer identities."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_mask_layer_removal import (
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

_LOGGER = get_logger("application.workflows.input_mask_restoration_service")


class InputMaskRestorationService:
    """Own snapshot-to-live Input mask identity restoration."""

    def __init__(
        self,
        *,
        document: InputCanvasDocumentPort,
        routes: InputRouteProjectionService,
        visuals: InputMaskVisualStateService,
    ) -> None:
        """Store live document, route, and visual-state collaborators."""

        self._document = document
        self._routes = routes
        self._visuals = visuals

    def restore(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        *,
        snapshot_mask_id: UUID,
        image_id: UUID,
        path: Path,
        association_key: tuple[str, str] | None,
    ) -> UUID | None:
        """Restore one mask and remap its snapshot id to the live layer id."""

        if not workflow_owns_input_image(workflow, image_id):
            log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=snapshot_mask_id,
                reason="foreign_restore_image",
            )
            return None
        self._routes.bind_scope_for_image(workflow_id, workflow, image_id)
        if self._document.contains_mask(image_id, snapshot_mask_id):
            if not self._routes.show_image(image_id):
                return None
            live_mask_id = snapshot_mask_id
            adopted = True
        else:
            if not self._routes.show_image(image_id):
                return None
            loaded_mask_id = self._document.load_mask_from_file(image_id, path)
            if loaded_mask_id is None:
                log_error(
                    _LOGGER,
                    "Input canvas restored mask file load failed",
                    workflow_id=workflow_id,
                    snapshot_mask_id=str(snapshot_mask_id),
                    image_id=str(image_id),
                    path=str(path),
                    association_key=association_key,
                    failure_reason="mask_file_load_returned_none",
                )
                return None
            live_mask_id = loaded_mask_id
            adopted = False
        _remap_restored_mask(
            workflow,
            snapshot_mask_id=snapshot_mask_id,
            live_mask_id=live_mask_id,
            image_id=image_id,
            association_key=association_key,
        )
        if association_key is not None:
            self._visuals.apply_materialized_opacity(
                workflow_id,
                workflow,
                association_key,
                live_mask_id,
            )
        active_mask_id = _valid_active_mask(workflow)
        self._routes.bind_scope(
            workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if active_mask_id == live_mask_id:
            self._routes.show_mask(image_id, live_mask_id)
        log_debug(
            _LOGGER,
            "Adopted editable Input mask restored from document archive"
            if adopted
            else "Restored input canvas mask",
            workflow_id=workflow_id,
            snapshot_mask_id=str(snapshot_mask_id),
            live_mask_id=str(live_mask_id),
            image_id=str(image_id),
            path=str(path),
            association_key=association_key,
        )
        return live_mask_id


def _valid_active_mask(workflow: WorkflowState) -> UUID | None:
    """Return an active mask only when it belongs to the active image."""

    mask_id = workflow.canvas.active_input_mask_uuid
    image_id = workflow.canvas.input_image_uuid
    if mask_id is None or image_id is None:
        return None
    if workflow.canvas.mask_image_owners().get(mask_id) == image_id:
        return mask_id
    workflow.canvas.active_input_mask_uuid = None
    return None


def _remap_restored_mask(
    workflow: WorkflowState,
    *,
    snapshot_mask_id: UUID,
    live_mask_id: UUID,
    image_id: UUID,
    association_key: tuple[str, str] | None,
) -> None:
    """Replace snapshot mask ids in workflow canvas state with live ids."""

    for collection in workflow.canvas.regional_mask_collections.values():
        regional_entry = collection.entry_for_mask(snapshot_mask_id)
        if regional_entry is None:
            continue
        collection.bind_mask_layer(regional_entry.region_id, live_mask_id)
        if workflow.canvas.active_input_mask_uuid in {None, snapshot_mask_id}:
            workflow.canvas.active_input_mask_uuid = live_mask_id
        return
    if association_key is not None:
        workflow.canvas.replace_mask_entry(association_key, live_mask_id, image_id)
    else:
        entry = workflow.canvas.mask_entry_for_id(snapshot_mask_id)
        if entry is not None:
            workflow.canvas.replace_mask_entry(
                entry.association_key,
                live_mask_id,
                image_id,
            )
    if workflow.canvas.active_input_mask_uuid in {None, snapshot_mask_id}:
        workflow.canvas.active_input_mask_uuid = live_mask_id


__all__ = ["InputMaskRestorationService"]
