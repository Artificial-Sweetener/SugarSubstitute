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

"""Own live Input image asset admission, claiming, and restoration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.input_route_projection_service import (
    InputRouteProjectionService,
)
from substitute.domain.workflow import WorkflowState


class InputImageAssetService:
    """Own Input image payload identity and workflow association."""

    def __init__(
        self,
        *,
        document: InputCanvasDocumentPort,
        routes: InputRouteProjectionService,
    ) -> None:
        """Store the Input document and authorized route owner."""

        self._document = document
        self._routes = routes

    def path_for(self, image_id: UUID) -> Path | None:
        """Return the exact persisted path owned by one loaded Input image."""

        return self._document.image_path(image_id)

    def load(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Replace one graph-owned image payload without replacing its identity."""

        workflow = workflows[active_workflow_id]
        existing_entry = workflow.canvas.image_entry(input_key)
        image_id = existing_entry.image_id if existing_entry is not None else uuid4()
        self._document.ensure_image_cached(image_id, image, path)
        workflow.canvas.bind_image(input_key, image_id)
        workflow.canvas.input_image_uuid = image_id
        self._routes.bind_scope(active_workflow_id, workflow)
        self._routes.show_image(image_id)
        return image_id

    def claim_loaded(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim a canvas-admitted Input image UUID without replacement."""

        workflow.canvas.replace_image_entry(input_key, image_id)
        workflow.canvas.input_image_uuid = image_id
        active_mask_id = workflow.canvas.active_input_mask_uuid
        owners = workflow.canvas.mask_image_owners()
        if active_mask_id is not None and owners.get(active_mask_id) != image_id:
            workflow.canvas.active_input_mask_uuid = None
            active_mask_id = None
        self._routes.bind_scope(
            workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if active_mask_id is not None:
            return self._routes.show_mask(image_id, active_mask_id)
        return self._routes.show_image(image_id)

    def restore(
        self,
        *,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Restore one Input image payload with a snapshot-owned UUID."""

        self._document.ensure_image_cached(image_id, image, path)


__all__ = ["InputImageAssetService"]
