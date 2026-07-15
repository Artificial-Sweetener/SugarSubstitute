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

from dataclasses import dataclass
from pathlib import Path
from substitute.domain.workflow import WorkflowState
from substitute.domain.workspace_snapshot import (
    EditorViewportSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.workspace_state.snapshot_normalization_service")
_SETTINGS_ROUTE = "settings"


@dataclass(frozen=True, slots=True)
class SnapshotNormalizationResult:
    """Describe a normalized workspace snapshot and non-fatal repairs."""

    snapshot: WorkspaceSnapshot
    warnings: tuple[str, ...]


class SnapshotNormalizationService:
    """Normalize snapshots so restore code receives coherent state."""

    def normalize(self, snapshot: WorkspaceSnapshot) -> SnapshotNormalizationResult:
        """Return a repaired workspace snapshot with warnings for dropped state."""

        warnings: list[str] = []
        log_info(
            _LOGGER,
            "snapshot normalization started",
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            tab_order=snapshot.tab_order,
            workflow_ids=tuple(workflow.workflow_id for workflow in snapshot.workflows),
        )
        workflows = self._normalize_workflows(snapshot.workflows, warnings)
        workflow_ids = {workflow.workflow_id for workflow in workflows}
        tab_order = self._normalize_tab_order(
            requested_tab_order=snapshot.tab_order,
            workflow_ids=workflow_ids,
            workflows=workflows,
            warnings=warnings,
        )
        active_route = self._normalize_active_route(
            requested_active_route=snapshot.active_route,
            tab_order=tab_order,
            workflow_ids=workflow_ids,
            warnings=warnings,
        )
        active_workflow_id = self._normalize_active_workflow_id(
            requested_active_workflow_id=snapshot.active_workflow_id,
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
    ) -> tuple[WorkflowSnapshot, ...]:
        """Drop duplicate or unusable workflows and normalize each survivor."""

        normalized: list[WorkflowSnapshot] = []
        seen_ids: set[str] = set()
        for workflow in workflows:
            if not workflow.workflow_id:
                warnings.append("Dropped workflow with missing id.")
                continue
            if workflow.workflow_id in seen_ids:
                warnings.append(
                    f"Dropped duplicate workflow id {workflow.workflow_id}."
                )
                continue
            seen_ids.add(workflow.workflow_id)
            normalized.append(self._normalize_workflow(workflow, warnings))
        return tuple(normalized)

    def _normalize_workflow(
        self,
        workflow: WorkflowSnapshot,
        warnings: list[str],
    ) -> WorkflowSnapshot:
        """Normalize cube order, image references, and focus fields for one tab."""

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
        input_images = tuple(
            image
            for image in workflow.input_images
            if self._path_exists(image.path, "input image", image.image_id, warnings)
        )
        input_image_ids = {image.image_id for image in input_images}
        input_masks = tuple(
            mask
            for mask in workflow.input_masks
            if mask.image_id in input_image_ids
            and self._path_exists(mask.path, "input mask", mask.mask_id, warnings)
        )
        output_images = tuple(
            image
            for image in workflow.output_images
            if self._path_exists(image.path, "output image", image.image_id, warnings)
        )
        output_uuid_texts = {image.image_id for image in output_images}
        normalized_state = self._normalize_workflow_state(
            workflow.workflow,
            stack_order=stack_order,
            output_uuid_texts=output_uuid_texts,
            warnings=warnings,
        )
        active_cube_alias = workflow.active_cube_alias
        if active_cube_alias not in set(stack_order):
            active_cube_alias = stack_order[-1] if stack_order else None
            warnings.append(
                f"Repaired active cube for workflow {workflow.workflow_id}."
            )
        editor_viewport = self._normalize_editor_viewport(
            workflow.editor_viewport,
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
        )

    def _normalize_editor_viewport(
        self,
        editor_viewport: EditorViewportSnapshot | None,
        *,
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
        output_uuid_texts: set[str],
        warnings: list[str],
    ) -> WorkflowState:
        """Return workflow state with stale output focus references repaired."""

        output_image_uuids = [
            image_id
            for image_id in state.output_image_uuids
            if str(image_id) in output_uuid_texts
        ]
        active_output_uuid = state.active_output_uuid
        if (
            active_output_uuid is not None
            and str(active_output_uuid) not in output_uuid_texts
        ):
            active_output_uuid = None
            warnings.append("Cleared stale active output UUID.")
        return WorkflowState(
            cubes=dict(state.cubes),
            stack_order=stack_order,
            metadata=dict(state.metadata),
            global_overrides={
                key: dict(value) for key, value in state.global_overrides.items()
            },
            override_control_states=dict(state.override_control_states),
            global_override_selections=dict(state.global_override_selections),
            canvas=state.canvas,
            output_image_uuids=output_image_uuids,
            output_focus_mode=state.output_focus_mode,
            active_output_uuid=active_output_uuid,
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
        warnings: list[str],
    ) -> tuple[str, ...]:
        """Return a tab order that references each workflow once."""

        ordered: list[str] = []
        for workflow_id in requested_tab_order:
            if workflow_id not in workflow_ids:
                warnings.append(
                    f"Removed stale workflow id {workflow_id} from tab order."
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

    def _path_exists(
        self,
        path: Path,
        subject: str,
        identifier: str,
        warnings: list[str],
    ) -> bool:
        """Return whether a snapshot path exists, recording drops."""

        if path.exists():
            return True
        warnings.append(f"Dropped missing {subject} {identifier}.")
        return False


__all__ = [
    "SnapshotNormalizationResult",
    "SnapshotNormalizationService",
]
