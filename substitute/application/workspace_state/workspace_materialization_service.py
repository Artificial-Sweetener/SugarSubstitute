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

"""Materialize normalized workspace snapshots through presentation ports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from substitute.domain.workflow import ImageMeta
from substitute.domain.workspace_snapshot import (
    ImageMetaSnapshot,
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
    WorkspaceSnapshot,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_info,
    log_warning,
)
from substitute.shared.startup_trace import trace_mark, trace_span

_LOGGER = get_logger("application.workspace_state.workspace_materialization_service")
_SETTINGS_ROUTE = "settings"


@dataclass(frozen=True, slots=True)
class SnapshotRestoreResult:
    """Describe non-fatal restore repairs and image load failures."""

    warnings: tuple[str, ...]


class WorkspaceMaterializationPort(Protocol):
    """Describe shell operations required for workspace materialization."""

    def reset_restored_workspace(self) -> None:
        """Clear current workflow tabs and workflow-scoped widgets."""

    def add_restored_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create one restored workflow tab and its workflow-scoped widgets."""

    def load_restored_input_image(self, path: Path) -> object | None:
        """Load an input image payload for restore."""

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Restore one input image payload under its snapshot UUID."""

    def restore_input_mask(
        self,
        reference: InputMaskReference,
    ) -> bool:
        """Restore one input mask reference when supported."""

    def load_restored_output_image(self, path: Path) -> object | None:
        """Load an output image payload for restore."""

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: ImageMeta,
    ) -> None:
        """Restore one output image payload under its snapshot UUID."""

    def project_restored_workflow(self, workflow_id: str) -> None:
        """Project one restored workflow route."""

    def project_restored_settings(self) -> None:
        """Project the restored Settings route."""

    def apply_restored_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Apply restored shell layout facts after widgets exist."""


class WorkspaceMaterializationService:
    """Own reusable workspace snapshot projection into a live shell."""

    def materialize(
        self,
        snapshot: WorkspaceSnapshot,
        port: WorkspaceMaterializationPort,
    ) -> SnapshotRestoreResult:
        """Materialize one normalized workspace snapshot through the supplied port."""

        return self._materialize(snapshot, port, reset_workspace=True)

    def materialize_into_existing_workspace(
        self,
        snapshot: WorkspaceSnapshot,
        port: WorkspaceMaterializationPort,
    ) -> SnapshotRestoreResult:
        """Append a snapshot into the current workspace without clearing tabs."""

        return self._materialize(snapshot, port, reset_workspace=False)

    def _materialize(
        self,
        snapshot: WorkspaceSnapshot,
        port: WorkspaceMaterializationPort,
        *,
        reset_workspace: bool,
    ) -> SnapshotRestoreResult:
        """Materialize one workspace snapshot with explicit reset behavior."""

        warnings: list[str] = []
        trace_mark(
            "workspace_materialization.start",
            reset_workspace=reset_workspace,
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            workflow_count=len(snapshot.workflows),
            shell_layout_present=snapshot.shell_layout is not None,
        )
        log_debug(
            _LOGGER,
            "workspace materialization started",
            reset_workspace=reset_workspace,
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            tab_order=snapshot.tab_order,
            workflow_ids=tuple(workflow.workflow_id for workflow in snapshot.workflows),
            shell_layout_present=snapshot.shell_layout is not None,
        )
        if reset_workspace:
            with trace_span("workspace_materialization.reset_workspace"):
                port.reset_restored_workspace()
        active_workflow_id = self._active_workflow_id(snapshot)
        log_debug(
            _LOGGER,
            "workspace materialization resolved active workflow",
            resolved_active_workflow_id=active_workflow_id,
            snapshot_active_route=snapshot.active_route,
            snapshot_active_workflow_id=snapshot.active_workflow_id,
            tab_order=snapshot.tab_order,
        )
        workflows_by_id = {
            workflow.workflow_id: workflow for workflow in snapshot.workflows
        }
        for workflow_id in snapshot.tab_order:
            workflow = workflows_by_id.get(workflow_id)
            if workflow is None:
                log_debug(
                    _LOGGER,
                    "workspace materialization skipped missing workflow",
                    workflow_id=workflow_id,
                )
                warnings.append(f"Skipped missing workflow {workflow_id}.")
                continue
            log_debug(
                _LOGGER,
                "workspace materialization adding workflow",
                workflow_id=workflow.workflow_id,
                tab_label=workflow.tab_label,
                activate=workflow.workflow_id == active_workflow_id,
                active_cube_alias=workflow.active_cube_alias,
                stack_order=tuple(workflow.workflow.stack_order),
                cube_count=len(workflow.workflow.cubes),
            )
            with trace_span(
                "workspace_materialization.workflow",
                workflow_id=workflow.workflow_id,
                activate=workflow.workflow_id == active_workflow_id,
                cube_count=len(workflow.workflow.cubes),
                stack_order_length=len(workflow.workflow.stack_order),
                input_image_count=len(workflow.input_images),
                input_mask_count=len(workflow.input_masks),
                output_image_count=len(workflow.output_images),
            ):
                port.add_restored_workflow(
                    workflow,
                    activate=workflow.workflow_id == active_workflow_id,
                )
                self._restore_input_images(workflow, port, warnings)
                self._restore_input_masks(workflow, port, warnings)
                self._restore_output_images(workflow, port, warnings)

        if active_workflow_id:
            log_debug(
                _LOGGER,
                "workspace materialization projecting workflow",
                workflow_id=active_workflow_id,
            )
            with trace_span(
                "workspace_materialization.project_workflow",
                workflow_id=active_workflow_id,
            ):
                port.project_restored_workflow(active_workflow_id)
        log_debug(
            _LOGGER,
            "workspace materialization applying shell layout",
            shell_layout_present=snapshot.shell_layout is not None,
        )
        log_debug(
            _LOGGER,
            "workspace materialization applying shell layout details",
            shell_layout_present=snapshot.shell_layout is not None,
            materialized_main_splitter_sizes=tuple(
                snapshot.shell_layout.main_splitter_sizes
            )
            if snapshot.shell_layout is not None
            else (),
            materialized_editor_output_splitter_sizes=tuple(
                snapshot.shell_layout.editor_output_splitter_sizes
            )
            if snapshot.shell_layout is not None
            else (),
            materialized_cube_stack_compact=snapshot.shell_layout.cube_stack_compact
            if snapshot.shell_layout is not None
            else None,
            materialized_cube_stack_width=snapshot.shell_layout.cube_stack_width
            if snapshot.shell_layout is not None
            else None,
            materialized_editor_panel_width=snapshot.shell_layout.editor_panel_width
            if snapshot.shell_layout is not None
            else None,
            materialized_canvas_panel_width=snapshot.shell_layout.canvas_panel_width
            if snapshot.shell_layout is not None
            else None,
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
        )
        with trace_span(
            "workspace_materialization.apply_shell_layout",
            shell_layout_present=snapshot.shell_layout is not None,
        ):
            port.apply_restored_shell_layout(snapshot.shell_layout)
        if snapshot.active_route == _SETTINGS_ROUTE:
            log_debug(
                _LOGGER,
                "workspace materialization projecting settings",
                active_workflow_id=active_workflow_id,
            )
            with trace_span("workspace_materialization.project_settings"):
                port.project_restored_settings()
        log_info(
            _LOGGER,
            "workspace materialization completed",
            warning_count=len(warnings),
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
        )
        for warning in warnings:
            log_warning(
                _LOGGER, "Materialized workspace snapshot with repair", repair=warning
            )
        trace_mark(
            "workspace_materialization.end",
            warning_count=len(warnings),
            workflow_count=len(snapshot.workflows),
            resolved_active_workflow_id=active_workflow_id,
        )
        return SnapshotRestoreResult(warnings=tuple(warnings))

    def _restore_input_images(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspaceMaterializationPort,
        warnings: list[str],
    ) -> None:
        """Load and restore input images for one workflow snapshot."""

        trace_mark(
            "workspace_materialization.input_images.start",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_images),
        )
        for reference in workflow.input_images:
            image = port.load_restored_input_image(reference.path)
            if image is None:
                warnings.append(
                    f"Skipped input image {reference.image_id} because it could not be loaded."
                )
                continue
            port.restore_input_image(reference, image)
        trace_mark(
            "workspace_materialization.input_images.end",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_images),
        )

    def _restore_input_masks(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspaceMaterializationPort,
        warnings: list[str],
    ) -> None:
        """Restore input masks through the shell when supported."""

        trace_mark(
            "workspace_materialization.input_masks.start",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_masks),
        )
        for reference in workflow.input_masks:
            if not port.restore_input_mask(reference):
                warnings.append(
                    f"Skipped input mask {reference.mask_id} because mask restore is unavailable."
                )
        trace_mark(
            "workspace_materialization.input_masks.end",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_masks),
        )

    def _restore_output_images(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspaceMaterializationPort,
        warnings: list[str],
    ) -> None:
        """Load and restore output images for one workflow snapshot."""

        trace_mark(
            "workspace_materialization.output_images.start",
            workflow_id=workflow.workflow_id,
            count=len(workflow.output_images),
        )
        for reference in workflow.output_images:
            image = port.load_restored_output_image(reference.path)
            if image is None:
                warnings.append(
                    f"Skipped output image {reference.image_id} because it could not be loaded."
                )
                continue
            port.restore_output_image(
                workflow.workflow_id,
                reference,
                image,
                _image_meta_from_snapshot(reference.metadata),
            )
        trace_mark(
            "workspace_materialization.output_images.end",
            workflow_id=workflow.workflow_id,
            count=len(workflow.output_images),
        )

    @staticmethod
    def _active_workflow_id(snapshot: WorkspaceSnapshot) -> str:
        """Return active workflow id from a normalized snapshot."""

        if snapshot.active_workflow_id in snapshot.tab_order:
            return snapshot.active_workflow_id
        return (
            snapshot.active_route if snapshot.active_route in snapshot.tab_order else ""
        )


def _image_meta_from_snapshot(snapshot: ImageMetaSnapshot) -> ImageMeta:
    """Build canvas output metadata from a snapshot value."""

    return ImageMeta(
        workflow_name=snapshot.workflow_name,
        cube_name=snapshot.cube_name,
        image_number=snapshot.image_number,
        suffix=snapshot.suffix,
        path=snapshot.path.as_posix(),
        source_key=snapshot.source_key,
        source_label=snapshot.source_label,
        node_id=snapshot.node_id,
        generation_run_id=snapshot.generation_run_id,
        prompt_id=snapshot.prompt_id,
        client_id=snapshot.client_id,
        list_index=snapshot.list_index,
        batch_index=snapshot.batch_index,
        scene_run_id=snapshot.scene_run_id or "",
        scene_key=snapshot.scene_key or "",
        scene_title=snapshot.scene_title or "",
        scene_order=snapshot.scene_order,
        scene_count=snapshot.scene_count,
        width=snapshot.width,
        height=snapshot.height,
        cube_execution_duration_ms=snapshot.cube_execution_duration_ms,
    )


__all__ = [
    "SnapshotRestoreResult",
    "WorkspaceMaterializationPort",
    "WorkspaceMaterializationService",
]
