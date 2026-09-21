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

"""Remove workflow-owned live mask layers with typed idempotent outcomes."""

from __future__ import annotations

from uuid import UUID

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_canvas_ports import (
    MaskLayerRemovalAuthorization,
    MaskLayerRemovalOutcome,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("application.workflows.input_mask_layer_removal")


def workflow_owns_input_image(workflow: WorkflowState, image_id: UUID) -> bool:
    """Return whether workflow-local Input state owns one image identity."""

    return workflow.canvas.image_entry_for_id(image_id) is not None


def mask_belongs_to_image(
    workflow: WorkflowState,
    mask_id: UUID,
    image_id: UUID,
) -> bool:
    """Return whether one complete mask entry proves layer ownership."""

    return workflow.canvas.owns_mask(mask_id, image_id)


def mask_ids_for_association(
    workflow: WorkflowState,
    association_key: tuple[str, str],
) -> tuple[UUID, ...]:
    """Return every materialized mask owned by one scalar or ordered node."""

    scalar = workflow.canvas.mask_entry(association_key)
    collection = workflow.canvas.regional_mask_collection(association_key)
    return (() if scalar is None else (scalar.mask_id,)) + (
        ()
        if collection is None
        else tuple(
            entry.mask_id for entry in collection.entries if entry.mask_id is not None
        )
    )


def authorize_workflow_mask_layer_removal(
    *,
    workflow_id: str,
    workflow: WorkflowState,
    image_id: UUID,
    mask_id: UUID,
) -> MaskLayerRemovalAuthorization | None:
    """Authorize an exact live-layer side effect while ownership still exists."""

    if not workflow.canvas.owns_mask(mask_id, image_id):
        log_warning(
            _LOGGER,
            "Rejected Input canvas state mutation",
            workflow_id=workflow_id,
            image_id=str(image_id),
            mask_id=str(mask_id),
            reason="foreign_mask_remove",
        )
        return None
    return MaskLayerRemovalAuthorization(
        workflow_id=workflow_id,
        image_id=image_id,
        mask_id=mask_id,
    )


def commit_workflow_mask_layer_removal(
    *,
    input_document: InputCanvasDocumentPort,
    authorization: MaskLayerRemovalAuthorization,
) -> MaskLayerRemovalOutcome:
    """Apply one authorized layer removal while treating absence as success."""

    removed = input_document.remove_mask_from_image(
        authorization.image_id,
        authorization.mask_id,
    )
    log_debug(
        _LOGGER,
        "Removed workflow-owned input canvas mask layer",
        workflow_id=authorization.workflow_id,
        image_id=str(authorization.image_id),
        mask_id=str(authorization.mask_id),
        removed=removed,
    )
    return (
        MaskLayerRemovalOutcome.REMOVED
        if removed
        else MaskLayerRemovalOutcome.ALREADY_ABSENT
    )


__all__ = [
    "authorize_workflow_mask_layer_removal",
    "commit_workflow_mask_layer_removal",
    "mask_belongs_to_image",
    "mask_ids_for_association",
    "workflow_owns_input_image",
]
