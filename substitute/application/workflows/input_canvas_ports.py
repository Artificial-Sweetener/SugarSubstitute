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

"""Define application ports shared by Input canvas orchestration services."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.domain.workflow import WorkflowAssetRef, WorkflowState


class InputCanvasStateServicePort(Protocol):
    """Describe Input canvas state capabilities used by graph reconciliation."""

    def load_input_image(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        input_key: str,
        image: object,
        path: Path,
    ) -> UUID:
        """Load one input image and return its live canvas UUID."""

    def load_mask_from_file(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        path: Path,
    ) -> UUID | None:
        """Load one mask from disk for an explicit target image."""

    def create_mask_for_image(
        self,
        workflow_id: str,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
        image_id: UUID,
        size: object,
    ) -> UUID | None:
        """Create one blank mask for an explicit target image."""

    def set_active_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        image_id: UUID,
    ) -> bool:
        """Persist and project one active Input image."""

    def claim_loaded_input_image(
        self,
        workflow_id: str,
        workflow: WorkflowState,
        input_key: str,
        image_id: UUID,
    ) -> bool:
        """Claim an existing QPane-loaded image for a workflow input key."""

    def drop_mask_association(
        self,
        active_workflow: WorkflowState,
        association_key: tuple[str, str],
    ) -> None:
        """Drop one stale mask association from canvas state and pane state."""

    def drop_input_surface(
        self,
        workflows: Mapping[str, WorkflowState],
        workflow_id: str,
        input_key: str,
    ) -> bool:
        """Drop one obsolete Input surface and its owned mask layers."""

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


class CanvasIoServicePort(Protocol):
    """Describe canvas IO capabilities used by workflow input reconciliation."""

    def load_input_image(self, path: Path) -> object | None:
        """Load one input image from disk."""

    def create_blank_input_surface(
        self,
        *,
        destination: Path,
        width: int,
        height: int,
    ) -> object | None:
        """Persist and load one blank Input canvas backing image."""

    def synthetic_input_surface_path(
        self,
        *,
        workflow_name: str,
        section_key: str,
        surface_key: str,
        width: int,
        height: int,
        projects_dir: Path,
    ) -> Path:
        """Return the deterministic project path for a synthetic backing image."""

    def expected_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Return the expected input-image-bound mask path."""

    def allocate_bound_mask_path(
        self,
        *,
        workflow_name: str,
        associated_image_path: Path,
        cube_alias: str,
        mask_node_name: str,
        image_size: tuple[int, int] | None,
        projects_dir: Path,
    ) -> Path:
        """Allocate a collision-safe input-image-bound mask path."""

    def image_dimensions(self, path: Path) -> tuple[int, int] | None:
        """Return image dimensions for a filesystem image."""

    def resolve_mask_path(
        self,
        *,
        workflow_name: str,
        path_from_buffer: str,
        projects_dir: Path,
    ) -> Path:
        """Resolve a previous mask buffer path for compatibility checks."""

    def create_blank_mask(self, *, destination: Path, size: object) -> bool:
        """Persist one blank mask file to disk."""


class WorkflowAssetServicePort(Protocol):
    """Describe asset ownership writes used by Input canvas materialization."""

    def input_image_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
    ) -> WorkflowAssetRef | None:
        """Return durable asset metadata for one input image node."""

    def associate_local_input_image(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
        image_path: Path | str,
    ) -> bool:
        """Associate one input image node with a user-selected local image file."""

    def associate_local_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
        mask_path: Path | str,
    ) -> bool:
        """Associate one input mask node with a user-selected local mask file."""

    def associate_project_input_mask(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
        relative_path: Path | str,
    ) -> bool:
        """Associate one input mask node with a project mask asset."""

    def input_mask_asset_ref(
        self,
        workflow: WorkflowState,
        *,
        section_key: str,
        node_name: str,
        field_key: str,
    ) -> WorkflowAssetRef | None:
        """Return durable asset metadata for one input mask node when present."""

    def resolve_input_mask_path(
        self,
        workflow: WorkflowState,
        *,
        workflow_name: str,
        section_key: str,
        node_name: str,
        field_key: str,
        projects_dir: Path,
    ) -> Path | None:
        """Resolve one input mask node from durable asset metadata."""


__all__ = [
    "CanvasIoServicePort",
    "InputCanvasStateServicePort",
    "WorkflowAssetServicePort",
]
