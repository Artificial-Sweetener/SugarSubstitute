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

"""Route node-card visual mask opacity through workflow and canvas owners."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeGuard
from uuid import UUID

from substitute.domain.workflow import WorkflowState
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("presentation.canvas.input.input_mask_visual_opacity_controller")


class _MaskBindingService(Protocol):
    """Expose the graph binding query needed for one mask node."""

    def binding_for_mask(
        self,
        workflow: WorkflowState,
        cube_alias: str,
        mask_node_name: str,
    ) -> object | None:
        """Return the authoritative binding for one mask node."""


class _MaskOpacityStateService(Protocol):
    """Expose the application mutation for node-level mask opacity."""

    def set_mask_visual_opacity(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Apply one node value to all associated materialized masks."""

    def mask_ids_for_association(
        self,
        workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> tuple[UUID, ...]:
        """Return every materialized mask owned by one graph mask node."""

    def synchronize_mask_visual_opacity_state(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        association_key: tuple[str, str],
        opacity: float,
    ) -> bool:
        """Adopt one opacity already restored by document history."""


class _MaskOpacityDocument(Protocol):
    """Expose the document history and restored layer presentation state."""

    def commit_mask_visual_opacity_edit(
        self,
        mask_ids: tuple[UUID, ...],
        *,
        before: float,
        after: float,
    ) -> bool:
        """Commit one already-previewed node gesture to document history."""

    def mask_visual_opacity(self, mask_id: UUID) -> float | None:
        """Return one materialized layer's current visual opacity."""


class InputMaskVisualOpacityController:
    """Apply editor-node opacity intent without making widgets authoritative."""

    def __init__(
        self,
        *,
        active_workflow: Callable[[], WorkflowState | None],
        active_workflow_id: Callable[[], str],
        binding_service: _MaskBindingService,
        state_service: _MaskOpacityStateService,
        document: _MaskOpacityDocument,
        project_opacity: Callable[[str, tuple[str, str], float], None],
        mark_changed: Callable[[str], None],
        request_autosave: Callable[[], None],
    ) -> None:
        """Store graph, workflow, document, and persistence boundaries."""

        self._active_workflow = active_workflow
        self._active_workflow_id = active_workflow_id
        self._binding_service = binding_service
        self._state_service = state_service
        self._document = document
        self._project_opacity = project_opacity
        self._mark_changed = mark_changed
        self._request_autosave = request_autosave
        self._applying_document_change = False

    def handle(self, cube_alias: str, node_name: str, opacity: float) -> bool:
        """Apply one active node's presentation value and persist the workflow."""

        active_context = self._active_context()
        if active_context is None:
            return False
        workflow_id, workflow = active_context
        association_key = self._association_key_for(
            workflow,
            workflow_id,
            cube_alias,
            node_name,
        )
        if association_key is None:
            return False
        self._applying_document_change = True
        try:
            applied = self._state_service.set_mask_visual_opacity(
                workflow_id,
                workflow,
                association_key,
                opacity,
            )
        finally:
            self._applying_document_change = False
        if not applied:
            return False
        self._mark_changed(workflow_id)
        self._request_autosave()
        return True

    def handle_commit(
        self,
        cube_alias: str,
        node_name: str,
        before: float,
        after: float,
    ) -> bool:
        """Commit one completed live gesture to chronological document history."""

        active_context = self._active_context()
        if active_context is None or before == after:
            return False
        workflow_id, workflow = active_context
        association_key = self._association_key_for(
            workflow,
            workflow_id,
            cube_alias,
            node_name,
        )
        if association_key is None:
            return False
        mask_ids = self._state_service.mask_ids_for_association(
            workflow,
            association_key,
        )
        self._applying_document_change = True
        try:
            committed = self._document.commit_mask_visual_opacity_edit(
                mask_ids,
                before=before,
                after=after,
            )
        finally:
            self._applying_document_change = False
        if not committed and mask_ids:
            log_warning(
                _LOGGER,
                "Failed to commit mask visual opacity to document history",
                workflow_id=workflow_id,
                association_key=association_key,
                mask_count=len(mask_ids),
                before=before,
                after=after,
            )
        return committed

    def reconcile_history(self, *_history_state: object) -> int:
        """Adopt node opacities restored by active CuteCanvas undo or redo."""

        active_context = self._active_context()
        if active_context is None or self._applying_document_change:
            return 0
        workflow_id, workflow = active_context
        synchronized: list[tuple[tuple[str, str], float]] = []
        for association_key in workflow.canvas.mask_association_keys():
            mask_ids = self._state_service.mask_ids_for_association(
                workflow,
                association_key,
            )
            opacities = tuple(
                self._document.mask_visual_opacity(mask_id) for mask_id in mask_ids
            )
            if (
                not opacities
                or opacities[0] is None
                or any(value != opacities[0] for value in opacities)
            ):
                continue
            opacity = opacities[0]
            if (
                opacity is None
                or not self._state_service.synchronize_mask_visual_opacity_state(
                    workflow_id,
                    workflow,
                    association_key,
                    opacity,
                )
            ):
                continue
            synchronized.append((association_key, opacity))
        if not synchronized:
            return 0
        for association_key, opacity in synchronized:
            self._project_opacity(workflow_id, association_key, opacity)
        self._mark_changed(workflow_id)
        self._request_autosave()
        return len(synchronized)

    def _active_context(self) -> tuple[str, WorkflowState] | None:
        """Resolve active workflow state only after startup establishes its ID."""

        workflow_id = self._active_workflow_id()
        if not workflow_id:
            return None
        try:
            workflow = self._active_workflow()
        except KeyError:
            log_warning(
                _LOGGER,
                "Skipped mask opacity intent for an unresolved workflow route",
                workflow_id=workflow_id,
                rejection_reason="workflow_route_not_materialized",
            )
            return None
        return None if workflow is None else (workflow_id, workflow)

    def _association_key_for(
        self,
        workflow: WorkflowState,
        workflow_id: str,
        cube_alias: str,
        node_name: str,
    ) -> tuple[str, str] | None:
        """Resolve one exact graph binding and report missing ownership."""

        binding = self._binding_service.binding_for_mask(
            workflow,
            cube_alias,
            node_name,
        )
        association_key = getattr(binding, "association_key", None)
        if _association_key(association_key):
            return association_key
        log_warning(
            _LOGGER,
            "Rejected mask visual opacity without an authoritative binding",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            node_name=node_name,
            rejection_reason="missing_mask_binding",
        )
        return None


def _association_key(value: object) -> TypeGuard[tuple[str, str]]:
    """Return whether one binding exposes a concrete graph association key."""

    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], str)
    )


__all__ = ["InputMaskVisualOpacityController"]
