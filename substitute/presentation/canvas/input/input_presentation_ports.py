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

"""Define narrow application and view ports for Input presentation owners."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.domain.workflow import InputCanvasPlan, WorkflowState


class WorkflowSessionPort(Protocol):
    """Expose active workflow identity and state to Input presenters."""

    active_workflow_id: str
    workflows: Mapping[str, WorkflowState]


class EditorMaskPickerPort(Protocol):
    """Expose scalar mask-picker projection on an editor panel."""

    def refresh_mask_picker(
        self,
        cube_alias: str,
        node_name: str,
        new_path: str,
    ) -> None:
        """Refresh one editor-panel mask picker preview."""


class InputImageWorkflowPort(Protocol):
    """Expose image materialization and reconciliation use cases."""

    def resolve_loaded_input_canvas_image_identity(
        self,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> object:
        """Resolve a canvas image id to a workflow graph input identity."""

    def materialize_input_image(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        image_node_name: str,
        image_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> object:
        """Materialize one input image and its editable masks."""

    def reconcile_loaded_input_canvas_image(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        image_node_name: str,
        image_id: UUID,
        image_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> object:
        """Associate one loaded image with workflow Input state."""

    def materialize_loaded_section(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        section_key: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> tuple[object, ...]:
        """Materialize editable Input images for one graph section."""


class InputMaskSelectionWorkflowPort(Protocol):
    """Expose user-selected scalar mask application."""

    def apply_user_selected_input_mask(
        self,
        *,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        cube_alias: str,
        mask_node_name: str,
        mask_path: str,
        workflow_name: str,
        projects_dir: Path,
    ) -> object:
        """Validate and apply one user-selected Input mask."""


class InputMaskPickerWorkflowPort(Protocol):
    """Expose authoritative scalar mask-picker projection data."""

    def input_canvas_plan(
        self,
        workflow: WorkflowState,
        section_key: str,
    ) -> InputCanvasPlan:
        """Return semantic image and mask bindings for one graph section."""

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        section_key: str,
        node_name: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve one mask path through semantic upload binding ownership."""


class InputImageStatePort(Protocol):
    """Expose active Input image path lookup."""

    def path_for(self, image_id: UUID) -> Path | None:
        """Return the persisted path associated with one Input image."""


class InputMaskActivationPort(Protocol):
    """Expose active workflow mask selection."""

    def set_active_workflow_mask(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        mask_id: UUID,
    ) -> bool:
        """Activate one workflow-owned Input mask."""


__all__ = [
    "EditorMaskPickerPort",
    "InputImageStatePort",
    "InputImageWorkflowPort",
    "InputMaskActivationPort",
    "InputMaskPickerWorkflowPort",
    "InputMaskSelectionWorkflowPort",
    "WorkflowSessionPort",
]
