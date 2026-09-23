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

"""Retire unreferenced Input image and mask assets."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_mask_asset_service import (
    InputMaskAssetService,
)
from substitute.application.workflows.input_route_projection_service import (
    InputRouteProjectionService,
)
from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_debug

_LOGGER = get_logger("application.workflows.input_asset_cleanup_service")


class InputAssetCleanupService:
    """Own workflow Input surface and unreferenced payload cleanup."""

    def __init__(
        self,
        *,
        document: InputCanvasDocumentPort,
        image_registry: CanvasImageRegistry,
        routes: InputRouteProjectionService,
        masks: InputMaskAssetService,
    ) -> None:
        """Store document, registry, route, and mask lifecycle owners."""

        self._document = document
        self._image_registry = image_registry
        self._routes = routes
        self._masks = masks

    def drop_surface(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        input_key: str,
    ) -> bool:
        """Drop one obsolete Input surface, mask layers, and cached image."""

        workflow = workflows.get(workflow_id)
        if workflow is None:
            return False
        image_entry = workflow.canvas.remove_image_entry(input_key)
        if image_entry is None:
            return False
        image_id = image_entry.image_id
        association_keys = tuple(
            entry.association_key
            for entry in workflow.canvas.mask_entries.values()
            if entry.image_id == image_id
        )
        for association_key in association_keys:
            self._masks.drop_association(workflow, association_key)
        collection_keys = tuple(
            association_key
            for association_key, collection in workflow.canvas.regional_mask_collections.items()
            if any(entry.image_id == image_id for entry in collection.entries)
        )
        regional_mask_ids: list[UUID] = []
        for association_key in collection_keys:
            collection = workflow.canvas.remove_regional_mask_collection(
                association_key
            )
            if collection is None:
                continue
            for entry in collection.entries:
                if entry.mask_id is None:
                    continue
                regional_mask_ids.append(entry.mask_id)
                self._document.remove_mask_from_image(image_id, entry.mask_id)
        if workflow.canvas.input_image_uuid == image_id:
            workflow.canvas.input_image_uuid = None
            workflow.canvas.active_input_mask_uuid = None
        self._routes.bind_scope(workflow_id, workflow)
        self._remove_if_unreferenced(image_id, workflows)
        log_debug(
            _LOGGER,
            "Dropped obsolete Input canvas surface",
            workflow_id=workflow_id,
            input_key=input_key,
            image_id=str(image_id),
            dropped_mask_count=len(association_keys),
            dropped_regional_mask_count=len(regional_mask_ids),
        )
        return True

    def prune_closed_workflow(
        self,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Remove closed-workflow Input payloads no workflow references."""

        for image_id in closed_workflow.canvas.image_ids():
            self._remove_if_unreferenced(image_id, remaining_workflows)

    def _remove_if_unreferenced(
        self,
        image_id: UUID,
        workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Prune one Input payload when no workflow references its UUID."""

        referenced = any(
            workflow.canvas.image_entry_for_id(image_id) is not None
            or image_id == workflow.canvas.input_image_uuid
            or image_id in workflow.output_image_uuids
            for workflow in workflows.values()
        )
        if referenced:
            return
        self._document.remove_unreferenced_image(image_id)
        self._image_registry.remove(image_id)


__all__ = ["InputAssetCleanupService"]
