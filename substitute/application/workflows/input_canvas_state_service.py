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

"""Own workflow-local Input canvas state mutation and route projection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.input_canvas_document_port import (
    InputCanvasDocumentPort,
)
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
    InputRouteProjectorPort,
    InputRouteScope,
    create_canvas_session_boundary,
)
from substitute.domain.workflow import CanvasKind, CanvasRouteIdentity, WorkflowState
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_error,
    log_warning,
)

_LOGGER = get_logger("application.workflows.input_canvas_state_service")


class InputCanvasStateService:
    """Mutate Input workflow state and apply authorized Input document routes."""

    def __init__(
        self,
        *,
        input_document: InputCanvasDocumentPort,
        input_route_projector: InputRouteProjectorPort,
        canvas_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
        image_registry: CanvasImageRegistry | None = None,
    ) -> None:
        """Store Input document, route, mask, and registry collaborators."""

        self._input_document = input_document
        self._input_route_projector = input_route_projector
        self._canvas_session_boundary = (
            canvas_session_boundary or create_canvas_session_boundary()
        )
        self._image_registry = image_registry or CanvasImageRegistry()

    def input_image_path(self, image_id: UUID) -> Path | None:
        """Return the exact persisted path owned by one loaded Input image."""

        return self._input_document.image_path(image_id)

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        """Project the active workflow's authorized Input image and mask route."""

        workflow = workflows.get(active_workflow_id)
        if workflow is None:
            self._bind_input_route_scope(active_workflow_id, None)
            self._input_route_projector.show_image(None)
            return

        image_id = self._valid_active_input_image(workflow)
        active_mask_id = self._valid_active_input_mask(workflow)
        self._bind_input_route_scope(
            active_workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if image_id is None:
            self._input_route_projector.show_image(None)
            return
        if active_mask_id is not None:
            self._input_route_projector.show_mask(image_id, active_mask_id)
            return
        self._input_route_projector.show_image(image_id)

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Persist and display an Input image owned by the active workflow."""

        if not self._workflow_owns_input_image(workflow, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=None,
                reason="foreign_input_image",
            )
            return False
        workflow.canvas.input_image_uuid = image_id
        active_mask_id = self._valid_active_input_mask(workflow)
        self._bind_input_route_scope(
            workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if active_mask_id is not None:
            return self._input_route_projector.show_mask(image_id, active_mask_id)
        return self._input_route_projector.show_image(image_id)

    def set_active_workflow_mask(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Persist and display an Input mask owned by the active input image."""

        image_id = workflow.canvas.input_image_uuid
        if image_id is None:
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=None,
                mask_id=mask_id,
                reason="missing_active_input_image",
            )
            return False
        if not self._mask_belongs_to_image(workflow, mask_id, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_input_mask",
            )
            return False
        workflow.canvas.active_input_mask_uuid = mask_id
        self._bind_input_route_scope(
            workflow_id,
            workflow,
            active_mask_id=mask_id,
        )
        return self._input_route_projector.show_mask(image_id, mask_id)

    def load_input_image(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Replace one graph-owned image payload without replacing its identity."""

        active_workflow = workflows[active_workflow_id]
        existing_entry = active_workflow.canvas.image_entry(input_key)
        image_id = existing_entry.image_id if existing_entry is not None else uuid4()
        self._input_document.ensure_image_cached(image_id, image, path)
        active_workflow.canvas.bind_image(input_key, image_id)
        active_workflow.canvas.input_image_uuid = image_id
        self._bind_input_route_scope(active_workflow_id, active_workflow)
        self._input_route_projector.show_image(image_id)
        return image_id

    def claim_loaded_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim a CuteCanvas-admitted Input image UUID without replacement."""

        workflow.canvas.replace_image_entry(input_key, image_id)
        workflow.canvas.input_image_uuid = image_id
        active_mask_id = self._valid_active_input_mask(workflow)
        self._bind_input_route_scope(
            workflow_id,
            workflow,
            active_mask_id=active_mask_id,
        )
        if active_mask_id is not None:
            return self._input_route_projector.show_mask(image_id, active_mask_id)
        return self._input_route_projector.show_image(image_id)

    def restore_input_image(
        self,
        *,
        image_id: UUID,
        image: object,
        path: Path | None,
    ) -> None:
        """Restore one Input image payload with a snapshot-owned UUID."""

        self._input_document.ensure_image_cached(image_id, image, path)

    def restore_input_mask(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        *,
        snapshot_mask_id: UUID,
        image_id: UUID,
        path: Path,
        association_key: tuple[str, str] | None,
    ) -> UUID | None:
        """Restore one Input mask and remap its snapshot id to the live layer id."""

        if not self._workflow_owns_input_image(active_workflow, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=snapshot_mask_id,
                reason="foreign_restore_image",
            )
            return None
        self._bind_input_route_scope_for_image(workflow_id, active_workflow, image_id)
        if self._input_document.contains_mask(image_id, snapshot_mask_id):
            self._remap_restored_input_mask(
                active_workflow,
                snapshot_mask_id=snapshot_mask_id,
                live_mask_id=snapshot_mask_id,
                image_id=image_id,
                association_key=association_key,
            )
            active_mask_id = self._valid_active_input_mask(active_workflow)
            self._bind_input_route_scope(
                workflow_id,
                active_workflow,
                active_mask_id=active_mask_id,
            )
            if active_mask_id == snapshot_mask_id:
                self._input_route_projector.show_mask(image_id, snapshot_mask_id)
            log_debug(
                _LOGGER,
                "Adopted editable Input mask restored from document archive",
                workflow_id=workflow_id,
                mask_id=str(snapshot_mask_id),
                image_id=str(image_id),
                association_key=association_key,
            )
            return snapshot_mask_id
        if not self._input_route_projector.show_image(image_id):
            return None
        live_mask_id = self._input_document.load_mask_from_file(image_id, path)
        if live_mask_id is None:
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

        self._remap_restored_input_mask(
            active_workflow,
            snapshot_mask_id=snapshot_mask_id,
            live_mask_id=live_mask_id,
            image_id=image_id,
            association_key=association_key,
        )
        active_mask_id = self._valid_active_input_mask(active_workflow)
        self._bind_input_route_scope(
            workflow_id,
            active_workflow,
            active_mask_id=active_mask_id,
        )
        if active_mask_id == live_mask_id:
            self._input_route_projector.show_mask(image_id, live_mask_id)
        log_debug(
            _LOGGER,
            "Restored input canvas mask",
            workflow_id=workflow_id,
            snapshot_mask_id=str(snapshot_mask_id),
            live_mask_id=str(live_mask_id),
            image_id=str(image_id),
            path=str(path),
            association_key=association_key,
        )
        return live_mask_id

    def create_mask_for_image(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        size: object,
    ) -> UUID | None:
        """Create one blank mask layer for an explicitly owned Input image."""

        if not self._workflow_owns_input_image(active_workflow, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=None,
                reason="foreign_mask_create_image",
            )
            return None
        self._bind_input_route_scope_for_image(workflow_id, active_workflow, image_id)
        if not self._input_route_projector.show_image(image_id):
            return None
        mask_id = self._input_document.create_blank_mask(image_id, size)
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
        active_workflow.canvas.bind_mask(association_key, mask_id, image_id)
        log_debug(
            _LOGGER,
            "Created input canvas mask layer for image",
            workflow_id=workflow_id,
            association_key=association_key,
            image_id=str(image_id),
            mask_id=str(mask_id),
        )
        return mask_id

    def load_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        path: Path,
    ) -> UUID | None:
        """Load one mask file layer for an explicitly owned Input image."""

        if not self._workflow_owns_input_image(active_workflow, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=None,
                reason="foreign_mask_load_image",
            )
            return None
        self._bind_input_route_scope_for_image(workflow_id, active_workflow, image_id)
        if not self._input_route_projector.show_image(image_id):
            return None
        mask_id = self._input_document.load_mask_from_file(image_id, path)
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
        active_workflow.canvas.bind_mask(association_key, mask_id, image_id)
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

    def update_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        mask_id: UUID,
        path: Path,
        image_dimensions: tuple[int, int] | None,
        mask_dimensions: tuple[int, int] | None,
    ) -> bool:
        """Update one associated mask layer after Input ownership validation."""

        if not self._workflow_owns_input_image(active_workflow, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_mask_update_image",
            )
            return False
        mask_entry = active_workflow.canvas.mask_entry(association_key)
        if mask_entry is None or mask_entry.mask_id != mask_id:
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="mask_update_association_mismatch",
            )
            return False
        if not self._mask_belongs_to_image(active_workflow, mask_id, image_id):
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="foreign_mask_update_mask",
            )
            return False
        if image_dimensions is None or mask_dimensions is None:
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="mask_update_unverified_dimensions",
            )
            return False
        if image_dimensions != mask_dimensions:
            self._log_input_rejection(
                workflow_id=workflow_id,
                image_id=image_id,
                mask_id=mask_id,
                reason="mask_update_dimensions_mismatch",
            )
            return False
        self._bind_input_route_scope_for_image(workflow_id, active_workflow, image_id)
        if not self._input_route_projector.show_image(image_id):
            return False
        updated = self._update_mask_layer_from_file(mask_id, path)
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

    def drop_mask_association(
        self,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Remove one stale mask association and detach its pane layer if unused."""

        entry = active_workflow.canvas.remove_mask_entry(association_key)
        if entry is None:
            return

        remaining_entry = active_workflow.canvas.mask_entry_for_id(entry.mask_id)
        if remaining_entry is not None:
            log_debug(
                _LOGGER,
                "Dropped shared input canvas mask association",
                association_key=association_key,
                image_id=str(entry.image_id),
                mask_id=str(entry.mask_id),
                pane_removed=False,
            )
            return
        if active_workflow.canvas.active_input_mask_uuid == entry.mask_id:
            active_workflow.canvas.active_input_mask_uuid = None
        removed = self._input_document.remove_mask_from_image(
            entry.image_id,
            entry.mask_id,
        )
        log_debug(
            _LOGGER,
            "Dropped input canvas mask association",
            association_key=association_key,
            image_id=str(entry.image_id),
            mask_id=str(entry.mask_id),
            pane_removed=removed,
        )

    def drop_input_surface(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        input_key: str,
    ) -> bool:
        """Drop one obsolete Input surface, its mask layers, and cached image."""

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
            self.drop_mask_association(workflow, association_key)
        if workflow.canvas.input_image_uuid == image_id:
            workflow.canvas.input_image_uuid = None
            workflow.canvas.active_input_mask_uuid = None
        self._bind_input_route_scope(workflow_id, workflow)
        self._remove_input_uuid_if_unreferenced(image_id, workflows)
        log_debug(
            _LOGGER,
            "Dropped obsolete Input canvas surface",
            workflow_id=workflow_id,
            input_key=input_key,
            image_id=str(image_id),
            dropped_mask_count=len(association_keys),
        )
        return True

    def prune_closed_workflow_images(
        self,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Remove closed-workflow Input catalog payloads no workflow references."""

        for image_uuid in closed_workflow.canvas.image_ids():
            self._remove_input_uuid_if_unreferenced(image_uuid, remaining_workflows)

    def _bind_input_route_scope(
        self,
        workflow_id: str,
        workflow: WorkflowState | None,
        *,
        active_mask_id: UUID | None = None,
    ) -> None:
        """Bind shared Input route scope for one workflow projection."""

        input_image_id = None if workflow is None else workflow.canvas.input_image_uuid
        input_session = self._canvas_session_boundary.bind_input_session(
            workflow_id=workflow_id,
            active_route=self._input_route_identity(input_image_id, active_mask_id),
        )
        self._input_route_projector.bind(
            InputRouteScope(
                session=input_session,
                allowed_image_ids=self._input_allowed_image_ids(workflow),
                allowed_mask_image_ids=self._input_allowed_mask_image_ids(workflow),
            )
        )

    def _bind_input_route_scope_for_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> None:
        """Bind Input scope for an explicit owned image operation."""

        session = self._canvas_session_boundary.bind_input_session(
            workflow_id=workflow_id,
            active_route=self._input_route_identity(image_id, None),
        )
        allowed_image_ids = set(self._input_allowed_image_ids(workflow))
        allowed_image_ids.add(image_id)
        self._input_route_projector.bind(
            InputRouteScope(
                session=session,
                allowed_image_ids=frozenset(allowed_image_ids),
                allowed_mask_image_ids=self._input_allowed_mask_image_ids(workflow),
            )
        )

    @staticmethod
    def _input_allowed_image_ids(workflow: WorkflowState | None) -> frozenset[UUID]:
        """Return workflow-owned Input image IDs allowed for display routes."""

        if workflow is None:
            return frozenset()
        image_ids = set(workflow.canvas.image_ids())
        return frozenset(image_ids)

    @staticmethod
    def _input_allowed_mask_image_ids(
        workflow: WorkflowState | None,
    ) -> Mapping[UUID, UUID]:
        """Return workflow mask ownership used to authorize mask activation."""

        if workflow is None:
            return {}
        return {
            entry.mask_id: entry.image_id
            for entry in workflow.canvas.mask_entries.values()
        }

    @classmethod
    def _input_route_identity(
        cls,
        image_id: UUID | None,
        mask_id: UUID | None,
    ) -> CanvasRouteIdentity:
        """Return the active Input route identity without renderer policy."""

        if image_id is None:
            return CanvasRouteIdentity.empty()
        return CanvasRouteIdentity(
            route_kind="input_image",
            route_key=cls._input_route_key(image_id, mask_id),
            primary_image_id=image_id,
        )

    @staticmethod
    def _input_route_key(image_id: UUID, mask_id: UUID | None) -> str:
        """Return a stable Input route key for an image and optional mask."""

        if mask_id is None:
            return f"image:{image_id}"
        return f"image:{image_id};mask:{mask_id}"

    def _valid_active_input_mask(self, workflow: WorkflowState) -> UUID | None:
        """Return active Input mask only when it belongs to the active image."""

        mask_id = workflow.canvas.active_input_mask_uuid
        if mask_id is None:
            return None
        mask_entry = workflow.canvas.mask_entry_for_id(mask_id)
        if mask_entry is None:
            workflow.canvas.active_input_mask_uuid = None
            return None
        if workflow.canvas.input_image_uuid is None:
            workflow.canvas.active_input_mask_uuid = None
            return None
        if mask_entry.image_id != workflow.canvas.input_image_uuid:
            workflow.canvas.active_input_mask_uuid = None
            return None
        return mask_id

    @staticmethod
    def _valid_active_input_image(workflow: WorkflowState) -> UUID | None:
        """Return active Input image only when workflow keyed state owns it."""

        image_id = workflow.canvas.input_image_uuid
        if image_id is None:
            return None
        if workflow.canvas.image_entry_for_id(image_id) is not None:
            return image_id
        workflow.canvas.input_image_uuid = None
        workflow.canvas.active_input_mask_uuid = None
        return None

    @staticmethod
    def _remap_restored_input_mask(
        workflow: WorkflowState,
        *,
        snapshot_mask_id: UUID,
        live_mask_id: UUID,
        image_id: UUID,
        association_key: tuple[str, str] | None,
    ) -> None:
        """Replace snapshot mask ids in workflow canvas state with live ids."""

        if association_key is not None:
            workflow.canvas.replace_mask_entry(
                association_key,
                live_mask_id,
                image_id,
            )
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

    @staticmethod
    def _workflow_owns_input_image(workflow: WorkflowState, image_id: UUID) -> bool:
        """Return whether workflow-local Input state owns image_id."""

        return workflow.canvas.image_entry_for_id(image_id) is not None

    @staticmethod
    def _mask_belongs_to_image(
        workflow: WorkflowState,
        mask_id: UUID,
        image_id: UUID,
    ) -> bool:
        """Return whether one complete mask entry proves mask ownership."""

        entry = workflow.canvas.mask_entry_for_id(mask_id)
        return entry is not None and entry.image_id == image_id

    def _remove_input_uuid_if_unreferenced(
        self,
        uuid_to_check: UUID,
        workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Prune Input catalog payloads when no workflow references the UUID."""

        is_referenced = any(
            workflow.canvas.image_entry_for_id(uuid_to_check) is not None
            or uuid_to_check == workflow.canvas.input_image_uuid
            or uuid_to_check in workflow.output_image_uuids
            for workflow in workflows.values()
        )
        if is_referenced:
            return

        self._input_document.remove_unreferenced_image(uuid_to_check)
        self._image_registry.remove(uuid_to_check)

    def _update_mask_layer_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Update mask pixels through the document's supported replacement API."""

        return self._input_document.replace_mask_from_file(mask_id, path)

    @staticmethod
    def _log_input_rejection(
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


__all__ = ["InputCanvasStateService"]
