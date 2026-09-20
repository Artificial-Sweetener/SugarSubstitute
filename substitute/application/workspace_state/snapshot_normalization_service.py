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

"""Repair restorable workspace snapshots before presentation materialization."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import UUID, uuid5

from substitute.domain.workflow import WorkflowDocumentKind, WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.workspace_state.snapshot_normalization_service")
_SETTINGS_ROUTE = "settings"
_WORKFLOW_MIGRATION_NAMESPACE = UUID("8a08a4bd-58f4-4b68-926f-1f4f56357d1c")


@dataclass(frozen=True, slots=True)
class SnapshotNormalizationResult:
    """Describe a normalized workspace snapshot and non-fatal repairs."""

    snapshot: WorkspaceSnapshot
    warnings: tuple[str, ...]


class SnapshotNormalizationService:
    """Normalize snapshots so restore code receives coherent state."""

    def normalize(self, snapshot: WorkspaceSnapshot) -> SnapshotNormalizationResult:
        """Return a repaired snapshot without discarding authoritative state."""

        warnings: list[str] = []
        log_info(
            _LOGGER,
            "snapshot normalization started",
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            tab_order=snapshot.tab_order,
            workflow_ids=tuple(workflow.workflow_id for workflow in snapshot.workflows),
        )
        workflows, identity_map = self._normalize_workflows(
            snapshot.workflows,
            warnings,
        )
        workflow_ids = {workflow.workflow_id for workflow in workflows}
        tab_order = self._normalize_tab_order(
            requested_tab_order=snapshot.tab_order,
            workflow_ids=workflow_ids,
            workflows=workflows,
            identity_map=identity_map,
            warnings=warnings,
        )
        active_route = self._normalize_active_route(
            requested_active_route=self._mapped_identity(
                snapshot.active_route,
                identity_map,
            ),
            tab_order=tab_order,
            workflow_ids=workflow_ids,
            warnings=warnings,
        )
        active_workflow_id = self._normalize_active_workflow_id(
            requested_active_workflow_id=self._mapped_identity(
                snapshot.active_workflow_id,
                identity_map,
            ),
            active_route=active_route,
            tab_order=tab_order,
            workflow_ids=workflow_ids,
            warnings=warnings,
        )
        normalized = WorkspaceSnapshot(
            schema_version=snapshot.schema_version,
            workflows=workflows,
            tab_order=tab_order,
            active_route=active_route,
            active_workflow_id=active_workflow_id,
            shell_layout=snapshot.shell_layout,
        )
        log_info(
            _LOGGER,
            "snapshot normalization completed",
            active_route=normalized.active_route,
            active_workflow_id=normalized.active_workflow_id,
            tab_order=normalized.tab_order,
            workflow_ids=tuple(
                workflow.workflow_id for workflow in normalized.workflows
            ),
            warning_count=len(warnings),
        )
        for warning in warnings:
            log_warning(_LOGGER, "Normalized workspace snapshot", repair=warning)
        return SnapshotNormalizationResult(
            snapshot=normalized, warnings=tuple(warnings)
        )

    def _normalize_workflows(
        self,
        workflows: tuple[WorkflowSnapshot, ...],
        warnings: list[str],
    ) -> tuple[tuple[WorkflowSnapshot, ...], dict[str, tuple[str, ...]]]:
        """Retain every workflow while assigning unique runtime identities."""

        normalized: list[WorkflowSnapshot] = []
        seen_ids: set[str] = set()
        identity_lists: dict[str, list[str]] = {}
        for index, workflow in enumerate(workflows):
            original_id = workflow.workflow_id
            workflow_id = original_id
            if not workflow_id or workflow_id in seen_ids:
                workflow_id = self._migration_workflow_id(
                    original_id=original_id,
                    ordinal=index,
                    occupied=seen_ids,
                )
                if original_id:
                    warnings.append(
                        f"Reassigned duplicate workflow id {original_id} to {workflow_id}."
                    )
                else:
                    warnings.append(f"Assigned missing workflow id {workflow_id}.")
            seen_ids.add(workflow_id)
            identity_lists.setdefault(original_id, []).append(workflow_id)
            normalized.append(
                self._normalize_workflow(
                    replace(workflow, workflow_id=workflow_id),
                    warnings,
                )
            )
        return tuple(normalized), {
            original: tuple(identities)
            for original, identities in identity_lists.items()
        }

    @staticmethod
    def _migration_workflow_id(
        *,
        original_id: str,
        ordinal: int,
        occupied: set[str],
    ) -> str:
        """Return a deterministic collision-free UUID for an ambiguous record."""

        salt = 0
        while True:
            candidate = str(
                uuid5(
                    _WORKFLOW_MIGRATION_NAMESPACE,
                    f"{original_id}\0{ordinal}\0{salt}",
                )
            )
            if candidate not in occupied:
                return candidate
            salt += 1

    @staticmethod
    def _mapped_identity(
        identity: str,
        identity_map: dict[str, tuple[str, ...]],
    ) -> str:
        """Map a legacy reference to its first retained workflow occurrence."""

        if not identity:
            return identity
        matches = identity_map.get(identity)
        return matches[0] if matches else identity

    def _normalize_workflow(
        self,
        workflow: WorkflowSnapshot,
        warnings: list[str],
    ) -> WorkflowSnapshot:
        """Normalize cube order, image references, and focus fields for one tab."""

        document_kind = workflow.workflow.document_kind
        existing_cube_aliases = set(workflow.workflow.cubes)
        stack_order = [
            alias
            for alias in workflow.workflow.stack_order
            if alias in existing_cube_aliases
        ]
        if stack_order != workflow.workflow.stack_order:
            warnings.append(
                f"Removed stale cube aliases from workflow {workflow.workflow_id}."
            )
        input_images = workflow.input_images
        input_masks = workflow.input_masks
        output_images = workflow.output_images
        for image in input_images:
            self._warn_unresolved_path(
                image.path,
                "input image",
                image.image_id,
                warnings,
            )
        for mask in input_masks:
            self._warn_unresolved_path(
                mask.path,
                "input mask",
                mask.mask_id,
                warnings,
            )
        for output_image in output_images:
            self._warn_unresolved_path(
                output_image.path,
                "output image",
                output_image.image_id,
                warnings,
            )
        normalized_state = self._normalize_workflow_state(
            workflow.workflow,
            stack_order=stack_order,
        )
        active_cube_alias = self._normalize_active_cube_alias(
            workflow,
            document_kind=document_kind,
            stack_order=stack_order,
            warnings=warnings,
        )
        editor_viewport = self._normalize_editor_viewport(
            workflow.editor_viewport,
            document_kind=document_kind,
            stack_order=stack_order,
            active_cube_alias=active_cube_alias,
            workflow_id=workflow.workflow_id,
            warnings=warnings,
        )
        return WorkflowSnapshot(
            workflow_id=workflow.workflow_id,
            tab_label=workflow.tab_label,
            workflow=normalized_state,
            active_cube_alias=active_cube_alias,
            input_images=input_images,
            input_masks=input_masks,
            output_images=output_images,
            editor_viewport=editor_viewport,
            document_dirty=workflow.document_dirty,
            document_source_path=workflow.document_source_path,
        )

    @staticmethod
    def _normalize_active_cube_alias(
        workflow: WorkflowSnapshot,
        *,
        document_kind: WorkflowDocumentKind,
        stack_order: list[str],
        warnings: list[str],
    ) -> str | None:
        """Return document-appropriate active cube focus state."""

        if document_kind is WorkflowDocumentKind.DIRECT_COMFY:
            return None
        active_cube_alias = workflow.active_cube_alias
        if active_cube_alias in set(stack_order):
            return active_cube_alias
        warnings.append(f"Repaired active cube for workflow {workflow.workflow_id}.")
        return stack_order[-1] if stack_order else None

    def _normalize_editor_viewport(
        self,
        editor_viewport: EditorViewportSnapshot | None,
        *,
        document_kind: WorkflowDocumentKind,
        stack_order: list[str],
        active_cube_alias: str | None,
        workflow_id: str,
        warnings: list[str],
    ) -> EditorViewportSnapshot | None:
        """Return coherent editor viewport state for one normalized workflow."""

        if editor_viewport is None:
            return None
        scroll_maximum = max(0, editor_viewport.scroll_maximum)
        scroll_value = min(max(0, editor_viewport.scroll_value), scroll_maximum)
        if document_kind is WorkflowDocumentKind.DIRECT_COMFY:
            return EditorViewportSnapshot(
                scroll_value=scroll_value,
                scroll_maximum=scroll_maximum,
                anchor_cube_alias=None,
            )
        anchor_cube_alias = editor_viewport.anchor_cube_alias
        if anchor_cube_alias not in set(stack_order):
            anchor_cube_alias = (
                active_cube_alias if active_cube_alias in stack_order else None
            )
            warnings.append(
                f"Repaired editor viewport anchor for workflow {workflow_id}."
            )
        return EditorViewportSnapshot(
            scroll_value=scroll_value,
            scroll_maximum=scroll_maximum,
            anchor_cube_alias=anchor_cube_alias,
        )

    def _normalize_workflow_state(
        self,
        state: WorkflowState,
        *,
        stack_order: list[str],
    ) -> WorkflowState:
        """Return a detached workflow state without discarding recoverable references."""

        return replace(
            state,
            cubes=dict(state.cubes),
            stack_order=stack_order,
            metadata=dict(state.metadata),
            global_overrides={
                key: dict(value) for key, value in state.global_overrides.items()
            },
            override_control_states=dict(state.override_control_states),
            global_override_selections=dict(state.global_override_selections),
            canvas=state.canvas,
            output_image_uuids=list(state.output_image_uuids),
            output_focus_mode=state.output_focus_mode,
            active_output_uuid=state.active_output_uuid,
            active_output_set_index=state.active_output_set_index,
            active_output_source_key=state.active_output_source_key,
            active_output_scene_key=state.active_output_scene_key,
            active_output_scene_overview=state.active_output_scene_overview,
            output_compare_state=state.output_compare_state,
        )

    def _normalize_tab_order(
        self,
        *,
        requested_tab_order: tuple[str, ...],
        workflow_ids: set[str],
        workflows: tuple[WorkflowSnapshot, ...],
        identity_map: dict[str, tuple[str, ...]],
        warnings: list[str],
    ) -> tuple[str, ...]:
        """Return a tab order that references each workflow once."""

        ordered: list[str] = []
        consumed: dict[str, int] = {}
        for requested_id in requested_tab_order:
            occurrence = consumed.get(requested_id, 0)
            mapped_ids = identity_map.get(requested_id, ())
            workflow_id = (
                mapped_ids[occurrence] if occurrence < len(mapped_ids) else requested_id
            )
            consumed[requested_id] = occurrence + 1
            if workflow_id not in workflow_ids:
                warnings.append(
                    f"Removed stale workflow id {requested_id} from tab order."
                )
                continue
            if workflow_id in ordered:
                warnings.append(
                    f"Removed duplicate workflow id {workflow_id} from tab order."
                )
                continue
            ordered.append(workflow_id)
        for workflow in workflows:
            if workflow.workflow_id not in ordered:
                ordered.append(workflow.workflow_id)
                warnings.append(
                    f"Appended missing workflow {workflow.workflow_id} to tab order."
                )
        return tuple(ordered)

    def _normalize_active_route(
        self,
        *,
        requested_active_route: str,
        tab_order: tuple[str, ...],
        workflow_ids: set[str],
        warnings: list[str],
    ) -> str:
        """Return an active route that presentation can project."""

        if requested_active_route == _SETTINGS_ROUTE:
            return requested_active_route
        if requested_active_route in workflow_ids:
            return requested_active_route
        if tab_order:
            warnings.append("Repaired active route to first workflow tab.")
            return tab_order[0]
        warnings.append("Repaired active route to blank workspace.")
        return ""

    def _normalize_active_workflow_id(
        self,
        *,
        requested_active_workflow_id: str,
        active_route: str,
        tab_order: tuple[str, ...],
        workflow_ids: set[str],
        warnings: list[str],
    ) -> str:
        """Return a valid active workflow id independent from the visible route."""

        if requested_active_workflow_id in workflow_ids:
            return requested_active_workflow_id
        if active_route in workflow_ids:
            warnings.append("Repaired active workflow id from active route.")
            return active_route
        if tab_order:
            warnings.append("Repaired active workflow id to first workflow tab.")
            return tab_order[0]
        if requested_active_workflow_id:
            warnings.append("Cleared stale active workflow id.")
        return ""

    @staticmethod
    def _warn_unresolved_path(
        path: Path,
        subject: str,
        identifier: str,
        warnings: list[str],
    ) -> None:
        """Record an unresolved path while retaining its authoritative reference."""

        if path.exists():
            return
        warnings.append(f"Retained unresolved {subject} {identifier}.")


__all__ = [
    "SnapshotNormalizationResult",
    "SnapshotNormalizationService",
]
