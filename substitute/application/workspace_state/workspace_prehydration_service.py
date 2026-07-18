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

"""Prehydrate safe workspace session chrome before the shell is visible."""

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

_LOGGER = get_logger("application.workspace_state.workspace_prehydration_service")


@dataclass(frozen=True, slots=True)
class WorkspacePrehydrationResult:
    """Describe non-fatal prehydration repairs and skipped assets."""

    warnings: tuple[str, ...]


class WorkspacePrehydrationPort(Protocol):
    """Describe shell operations safe before first visible restore finalization."""

    def begin_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Enter prehydration mode for one normalized workspace snapshot."""

    def reset_restored_workspace(self) -> None:
        """Clear current workflow tabs and workflow-scoped widgets."""

    def add_prehydrated_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create workflow session/tab chrome without projecting the editor."""

    def load_restored_input_image(self, path: Path) -> object | None:
        """Load one input image payload for restore."""

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Restore one input image payload under its snapshot UUID."""

    def restore_input_mask(self, reference: InputMaskReference) -> bool:
        """Restore one input mask reference when supported."""

    def load_restored_output_image(self, path: Path) -> object | None:
        """Load one output image payload for restore."""

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: ImageMeta,
    ) -> None:
        """Restore one output image payload under its snapshot UUID."""

    def remember_prehydrated_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Remember shell layout for visible finalization."""

    def finish_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Leave prehydration with enough state for visible finalization."""


class WorkspacePrehydrationService:
    """Own safe pre-show workspace session materialization."""

    def prehydrate(
        self,
        snapshot: WorkspaceSnapshot,
        port: WorkspacePrehydrationPort,
    ) -> WorkspacePrehydrationResult:
        """Prehydrate workflow chrome and local assets without editor projection."""

        warnings: list[str] = []
        active_workflow_id = self._active_workflow_id(snapshot)
        trace_mark(
            "workspace_prehydration.start",
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
            workflow_count=len(snapshot.workflows),
            shell_layout_present=snapshot.shell_layout is not None,
        )
        log_debug(
            _LOGGER,
            "workspace prehydration started",
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
            tab_order=snapshot.tab_order,
            workflow_count=len(snapshot.workflows),
            shell_layout_present=snapshot.shell_layout is not None,
        )
        port.begin_prehydrated_restore(snapshot)
        port.reset_restored_workspace()
        workflows_by_id = {
            workflow.workflow_id: workflow for workflow in snapshot.workflows
        }
        for workflow_id in snapshot.tab_order:
            workflow = workflows_by_id.get(workflow_id)
            if workflow is None:
                warnings.append(f"Skipped missing workflow {workflow_id}.")
                continue
            activate = workflow.workflow_id == active_workflow_id
            with trace_span(
                "workspace_prehydration.workflow",
                workflow_id=workflow.workflow_id,
                activate=activate,
                input_image_count=len(workflow.input_images),
                input_mask_count=len(workflow.input_masks),
                output_image_count=len(workflow.output_images),
            ):
                port.add_prehydrated_workflow(workflow, activate=activate)
                self._restore_input_images(workflow, port, warnings)
                self._restore_input_masks(workflow, port, warnings)
                self._restore_output_images(workflow, port, warnings)
        port.remember_prehydrated_shell_layout(snapshot.shell_layout)
        port.finish_prehydrated_restore(snapshot)
        log_info(
            _LOGGER,
            "workspace prehydration completed",
            warning_count=len(warnings),
            active_route=snapshot.active_route,
            active_workflow_id=snapshot.active_workflow_id,
            resolved_active_workflow_id=active_workflow_id,
        )
        for warning in warnings:
            log_warning(
                _LOGGER,
                "Prehydrated workspace snapshot with repair",
                repair=warning,
            )
        trace_mark(
            "workspace_prehydration.end",
            warning_count=len(warnings),
            workflow_count=len(snapshot.workflows),
        )
        return WorkspacePrehydrationResult(warnings=tuple(warnings))

    def _restore_input_images(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspacePrehydrationPort,
        warnings: list[str],
    ) -> None:
        """Load and restore input images for one workflow snapshot."""

        trace_mark(
            "workspace_prehydration.input_images.start",
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
            "workspace_prehydration.input_images.end",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_images),
        )

    def _restore_input_masks(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspacePrehydrationPort,
        warnings: list[str],
    ) -> None:
        """Restore input masks through the shell when supported."""

        trace_mark(
            "workspace_prehydration.input_masks.start",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_masks),
        )
        for reference in workflow.input_masks:
            if not port.restore_input_mask(reference):
                warnings.append(
                    f"Skipped input mask {reference.mask_id} because mask restore is unavailable."
                )
        trace_mark(
            "workspace_prehydration.input_masks.end",
            workflow_id=workflow.workflow_id,
            count=len(workflow.input_masks),
        )

    def _restore_output_images(
        self,
        workflow: WorkflowSnapshot,
        port: WorkspacePrehydrationPort,
        warnings: list[str],
    ) -> None:
        """Load and restore output images for one workflow snapshot."""

        trace_mark(
            "workspace_prehydration.output_images.start",
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
            "workspace_prehydration.output_images.end",
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
    "WorkspacePrehydrationPort",
    "WorkspacePrehydrationResult",
    "WorkspacePrehydrationService",
]
