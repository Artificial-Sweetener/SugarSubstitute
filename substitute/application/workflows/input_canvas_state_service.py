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
from typing import Protocol
from uuid import UUID, uuid4

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_pane_catalog_port import (
    InputCanvasPaneCatalogPort,
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


class InputMaskPanePort(Protocol):
    """Describe Input QPane mask-layer APIs owned by Input canvas state."""

    def createBlankMask(self, size: object) -> UUID | None:  # noqa: N802
        """Create a blank mask for the current pane image."""

    def loadMaskFromFile(self, path: str) -> UUID | None:  # noqa: N802
        """Load one mask layer from a filesystem path."""

    def removeMaskFromImage(self, image_id: UUID, mask_id: UUID) -> bool:  # noqa: N802
        """Remove one mask layer from its owning image."""


class InputCanvasStateService:
    """Mutate Input workflow state and apply authorized Input QPane routes."""

    def __init__(
        self,
        *,
        input_pane: InputMaskPanePort,
        input_catalog: InputCanvasPaneCatalogPort,
        input_route_projector: InputRouteProjectorPort,
        canvas_session_boundary: CanvasRouteSessionBoundaryPort | None = None,
        image_registry: CanvasImageRegistry | None = None,
    ) -> None:
        """Store Input-only catalog, route, mask, and registry collaborators."""

        self._input_pane = input_pane
        self._input_catalog = input_catalog
        self._input_route_projector = input_route_projector
        self._canvas_session_boundary = (
            canvas_session_boundary or create_canvas_session_boundary()
        )
        self._image_registry = image_registry or CanvasImageRegistry()

    def input_image_path(self, image_id: UUID) -> Path | None:
        """Return the exact persisted path owned by one loaded Input image."""

        return self._input_catalog.image_path(image_id)

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
        """Load one Input image payload and associate it with a graph input key."""

        active_workflow = workflows[active_workflow_id]
        new_id = uuid4()
        old_uuid = active_workflow.canvas.input_key_map.get(input_key)
        self._input_catalog.ensure_image_cached(new_id, image, path)
        active_workflow.canvas.input_key_map[input_key] = new_id
        active_workflow.canvas.input_image_uuid = new_id
        self._bind_input_route_scope(active_workflow_id, active_workflow)
        if old_uuid is not None:
            self._remove_input_uuid_if_unreferenced(old_uuid, workflows)
        self._input_route_projector.show_image(new_id)
        return new_id

    def claim_loaded_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim a QPane-loaded Input image UUID without allocating a replacement."""

        workflow.canvas.input_key_map[input_key] = image_id
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

        self._input_catalog.ensure_image_cached(image_id, image, path)

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
        if not self._input_route_projector.show_image(image_id):
            return None
        live_mask_id = self._input_pane.loadMaskFromFile(str(path))
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
        mask_id = self._input_pane.createBlankMask(size)
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
        active_workflow.canvas.mask_associations[association_key] = mask_id
        active_workflow.canvas.mask_to_image_map[mask_id] = image_id
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
        mask_id = self._input_pane.loadMaskFromFile(str(path))
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
        active_workflow.canvas.mask_associations[association_key] = mask_id
        active_workflow.canvas.mask_to_image_map[mask_id] = image_id
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
        if active_workflow.canvas.mask_associations.get(association_key) != mask_id:
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

        mask_id = active_workflow.canvas.mask_associations.pop(association_key, None)
        if mask_id is None:
            return

        if active_workflow.canvas.active_input_mask_uuid == mask_id:
            active_workflow.canvas.active_input_mask_uuid = None
        image_id = active_workflow.canvas.mask_to_image_map.get(mask_id)
        if mask_id in active_workflow.canvas.mask_associations.values():
            log_debug(
                _LOGGER,
                "Dropped mask association while preserving shared mask layer",
                association_key=association_key,
                image_id=str(image_id) if image_id is not None else "",
                mask_id=str(mask_id),
            )
            return
        active_workflow.canvas.mask_to_image_map.pop(mask_id, None)

        if image_id is None:
            log_warning(
                _LOGGER,
                "Dropped mask association without image mapping",
                association_key=association_key,
                mask_id=str(mask_id),
            )
            return

        removed = self._input_pane.removeMaskFromImage(image_id, mask_id)
        log_debug(
            _LOGGER,
            "Dropped input canvas mask association",
            association_key=association_key,
            image_id=str(image_id),
            mask_id=str(mask_id),
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
        image_id = workflow.canvas.input_key_map.pop(input_key, None)
        if image_id is None:
            return False
        association_keys = tuple(
            association_key
            for association_key, mask_id in workflow.canvas.mask_associations.items()
            if workflow.canvas.mask_to_image_map.get(mask_id) == image_id
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

        for image_uuid in list(closed_workflow.canvas.input_key_map.values()):
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
        image_ids = set(workflow.canvas.input_key_map.values())
        return frozenset(image_ids)

    @staticmethod
    def _input_allowed_mask_image_ids(
        workflow: WorkflowState | None,
    ) -> Mapping[UUID, UUID]:
        """Return workflow mask ownership used to authorize mask activation."""

        if workflow is None:
            return {}
        return dict(workflow.canvas.mask_to_image_map)

    @classmethod
    def _input_route_identity(
        cls,
        image_id: UUID | None,
        mask_id: UUID | None,
    ) -> CanvasRouteIdentity:
        """Return the active Input route identity without QPane policy."""

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
        if mask_id not in workflow.canvas.mask_associations.values():
            workflow.canvas.active_input_mask_uuid = None
            return None
        image_id = workflow.canvas.mask_to_image_map.get(mask_id)
        if workflow.canvas.input_image_uuid is None:
            workflow.canvas.active_input_mask_uuid = None
            return None
        if image_id != workflow.canvas.input_image_uuid:
            workflow.canvas.active_input_mask_uuid = None
            return None
        return mask_id

    @staticmethod
    def _valid_active_input_image(workflow: WorkflowState) -> UUID | None:
        """Return active Input image only when workflow keyed state owns it."""

        image_id = workflow.canvas.input_image_uuid
        if image_id is None:
            return None
        if image_id in workflow.canvas.input_key_map.values():
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

        workflow.canvas.mask_to_image_map.pop(snapshot_mask_id, None)
        workflow.canvas.mask_to_image_map[live_mask_id] = image_id

        if association_key is not None:
            workflow.canvas.mask_associations[association_key] = live_mask_id
        else:
            for key, value in tuple(workflow.canvas.mask_associations.items()):
                if value == snapshot_mask_id:
                    workflow.canvas.mask_associations[key] = live_mask_id

        if workflow.canvas.active_input_mask_uuid in {None, snapshot_mask_id}:
            workflow.canvas.active_input_mask_uuid = live_mask_id

    @staticmethod
    def _workflow_owns_input_image(workflow: WorkflowState, image_id: UUID) -> bool:
        """Return whether workflow-local Input state owns image_id."""

        return image_id in workflow.canvas.input_key_map.values()

    @staticmethod
    def _mask_belongs_to_image(
        workflow: WorkflowState,
        mask_id: UUID,
        image_id: UUID,
    ) -> bool:
        """Return whether mask_to_image_map proves mask ownership."""

        return (
            mask_id in workflow.canvas.mask_associations.values()
            and workflow.canvas.mask_to_image_map.get(mask_id) == image_id
        )

    def _remove_input_uuid_if_unreferenced(
        self,
        uuid_to_check: UUID,
        workflows: Mapping[str, WorkflowState],
    ) -> None:
        """Prune Input catalog payloads when no workflow references the UUID."""

        is_referenced = any(
            uuid_to_check in workflow.canvas.input_key_map.values()
            or uuid_to_check == workflow.canvas.input_image_uuid
            or uuid_to_check in workflow.output_image_uuids
            for workflow in workflows.values()
        )
        if is_referenced:
            return

        self._input_catalog.remove_unreferenced_image(uuid_to_check)
        self._image_registry.remove(uuid_to_check)

    def _update_mask_layer_from_file(self, mask_id: UUID, path: Path) -> bool:
        """Update mask pixels through public QPane mask-layer collaborators."""

        controller = getattr(self._input_pane, "mask_controller", None)
        update_mask = getattr(controller, "update_mask_from_file", None)
        if callable(update_mask):
            return bool(update_mask(mask_id, str(path)))

        catalog = getattr(self._input_pane, "catalog", None)
        if not callable(catalog):
            log_warning(
                _LOGGER,
                "Input canvas mask update skipped because catalog API is unavailable",
                mask_id=str(mask_id),
                path=str(path),
            )
            return False
        mask_catalog = catalog()
        mask_manager = (
            getattr(mask_catalog, "maskManager", lambda: None)()
            if mask_catalog is not None
            else None
        )
        fallback_update = (
            getattr(mask_manager, "update_mask_from_file", None)
            if mask_manager is not None
            else None
        )
        if callable(fallback_update):
            return bool(fallback_update(mask_id, str(path)))

        log_warning(
            _LOGGER,
            "Input canvas mask update skipped because mask update API is unavailable",
            mask_id=str(mask_id),
            path=str(path),
        )
        return False

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


__all__ = ["InputCanvasStateService", "InputMaskPanePort"]
