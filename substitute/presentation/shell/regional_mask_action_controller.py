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

"""Coordinate editor-panel regional mask actions through application owners."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from substitute.application.workflows.ordered_mask_region_authoring_service import (
    OrderedMaskRegionAuthoringService,
)
from substitute.application.workflows.input_route_projection_service import (
    InputRouteProjectionService,
)
from substitute.domain.workflow import WorkflowState
from substitute.presentation.regional.mask_collection_presenter import (
    RegionalMaskCollectionPresenter,
)
from substitute.presentation.regional.mask_editor_actions import (
    RegionalMaskActionOutcome,
    parse_regional_mask_action,
)


class RegionalMaskActionController:
    """Apply add, import, and remove intent to one active regional collection."""

    def __init__(
        self,
        *,
        active_workflow: Callable[[], WorkflowState | None],
        active_workflow_id: Callable[[], str],
        workflow_name: Callable[[str], str],
        projects_dir: Callable[[], Path],
        region_authoring: OrderedMaskRegionAuthoringService,
        input_routes: InputRouteProjectionService,
        presenter: RegionalMaskCollectionPresenter,
        accept_canvas_selection: Callable[[], bool],
    ) -> None:
        """Capture active session, application, filesystem, and view boundaries."""

        self._active_workflow = active_workflow
        self._active_workflow_id = active_workflow_id
        self._workflow_name = workflow_name
        self._projects_dir = projects_dir
        self._region_authoring = region_authoring
        self._input_routes = input_routes
        self._presenter = presenter
        self._accept_canvas_selection = accept_canvas_selection

    def handle(
        self,
        cube_alias: str,
        node_name: str,
        action: str,
    ) -> RegionalMaskActionOutcome:
        """Apply one encoded widget action through its focused durable owners."""

        if not action.startswith("@region:"):
            return RegionalMaskActionOutcome(False)
        request = parse_regional_mask_action(action)
        if request is None:
            return RegionalMaskActionOutcome(True)
        if request.kind == "add":
            changed = self.add(cube_alias, node_name) is not None
            return RegionalMaskActionOutcome(True, changed)
        if request.kind == "import":
            assert request.path is not None
            changed = self.import_mask(cube_alias, node_name, request.path) is not None
            return RegionalMaskActionOutcome(True, changed)
        if request.kind == "remove":
            assert request.index is not None
            changed = self.remove(cube_alias, node_name, request.index)
            return RegionalMaskActionOutcome(True, changed)
        assert request.index is not None
        changed = self.select_region(cube_alias, node_name, request.index)
        return RegionalMaskActionOutcome(True, changed)

    def select_region(self, cube_alias: str, node_name: str, index: int) -> bool:
        """Select one ordered node row and its exact CuteCanvas mask layer."""

        workflow = self._active_workflow()
        if workflow is None:
            return False
        association_key = (cube_alias, node_name)
        collection = workflow.canvas.regional_mask_collection(association_key)
        if collection is None or not 0 <= index < len(collection.entries):
            return False
        entry = collection.entries[index]
        if entry.mask_id is None:
            return False
        collection.select(entry.region_id)
        if not self._input_routes.set_active_mask(
            self._active_workflow_id(),
            workflow,
            entry.mask_id,
        ):
            return False
        self._presenter.refresh(association_key)
        return True

    def select_canvas_mask(self, mask_id: object) -> bool:
        """Synchronize a CuteCanvas-selected mask with durable region selection."""

        if not self._accept_canvas_selection() or not isinstance(mask_id, UUID):
            return False
        workflow = self._active_workflow()
        if workflow is None:
            return False
        image_id = workflow.canvas.input_image_uuid
        if image_id is None or not workflow.canvas.owns_mask(mask_id, image_id):
            return False
        selected_key: tuple[str, str] | None = None
        selected_region_id: UUID | None = None
        for (
            association_key,
            collection,
        ) in workflow.canvas.regional_mask_collections.items():
            entry = collection.entry_for_mask(mask_id)
            if entry is None:
                continue
            selected_key = association_key
            selected_region_id = entry.region_id
            break
        selection_is_current = workflow.canvas.active_input_mask_uuid == mask_id and (
            selected_key is None
            or workflow.canvas.regional_mask_collections[
                selected_key
            ].selected_region_id
            == selected_region_id
        )
        if selection_is_current:
            return True
        if selected_key is not None and selected_region_id is not None:
            workflow.canvas.regional_mask_collections[selected_key].select(
                selected_region_id
            )
        if not self._input_routes.set_active_mask(
            self._active_workflow_id(),
            workflow,
            mask_id,
        ):
            return False
        if selected_key is not None:
            self._presenter.refresh(selected_key)
        return True

    def add(self, cube_alias: str, node_name: str) -> UUID | None:
        """Append one blank region and refresh its authoritative linked views."""

        workflow = self._active_workflow()
        if workflow is None:
            return None
        workflow_id = self._active_workflow_id()
        mask_id = self._region_authoring.add_region(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=cube_alias,
            node_name=node_name,
            workflow_name=self._workflow_name(workflow_id),
            projects_dir=self._projects_dir(),
        )
        if mask_id is not None:
            self._presenter.refresh((cube_alias, node_name))
        return mask_id

    def import_mask(
        self,
        cube_alias: str,
        node_name: str,
        mask_path: str,
    ) -> UUID | None:
        """Import one normalized region and refresh its authoritative linked views."""

        workflow = self._active_workflow()
        if workflow is None:
            return None
        workflow_id = self._active_workflow_id()
        mask_id = self._region_authoring.import_region(
            workflow=workflow,
            workflow_id=workflow_id,
            section_key=cube_alias,
            node_name=node_name,
            source_path=Path(mask_path),
            workflow_name=self._workflow_name(workflow_id),
            projects_dir=self._projects_dir(),
        )
        if mask_id is not None:
            self._presenter.refresh((cube_alias, node_name))
        return mask_id

    def remove(self, cube_alias: str, node_name: str, region_index: int) -> bool:
        """Remove one exact region and refresh its authoritative linked views."""

        workflow = self._active_workflow()
        if workflow is None:
            return False
        removed = self._region_authoring.remove_region(
            workflow=workflow,
            workflow_id=self._active_workflow_id(),
            section_key=cube_alias,
            node_name=node_name,
            region_index=region_index,
        )
        if removed:
            self._presenter.refresh((cube_alias, node_name))
        return removed


__all__ = ["RegionalMaskActionController"]
