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

"""Adapt shell restore owners to the workspace materialization application port."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from substitute.application.workflows import ImageMeta
from substitute.domain.workspace_snapshot import (
    InputImageReference,
    InputMaskReference,
    OutputImageReference,
    ShellLayoutSnapshot,
    WorkflowSnapshot,
)


class ShellWorkspaceMaterializationPort:
    """Expose only restored workspace materialization operations to the application."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that owns the composed restore collaborators."""

        self._shell = shell

    def reset_restored_workspace(self) -> None:
        """Clear current workflow tabs and workflow-scoped widgets."""

        self._shell.restored_workflow_materializer.reset_restored_workspace()

    def add_restored_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create one restored workflow tab and its workflow-scoped widgets."""

        self._shell.restored_workflow_materializer.add_restored_workflow(
            snapshot,
            activate=activate,
        )

    def load_restored_input_image(self, path: Path) -> object | None:
        """Load an input image payload for restore."""

        return cast(
            object | None,
            self._shell.workspace_restore_image_adapter.load_restored_input_image(path),
        )

    def restore_input_image(
        self,
        reference: InputImageReference,
        image: object,
    ) -> None:
        """Restore one input image payload under its snapshot UUID."""

        self._shell.workspace_restore_image_adapter.restore_input_image(
            reference,
            image,
        )

    def restore_input_mask(self, reference: InputMaskReference) -> bool:
        """Restore one input mask reference when supported."""

        return bool(
            self._shell.workspace_restore_image_adapter.restore_input_mask(reference)
        )

    def load_restored_output_image(self, path: Path) -> object | None:
        """Load an output image payload for restore."""

        return cast(
            object | None,
            self._shell.workspace_restore_image_adapter.load_restored_output_image(
                path
            ),
        )

    def restore_output_image(
        self,
        workflow_id: str,
        reference: OutputImageReference,
        image: object,
        image_meta: ImageMeta,
    ) -> None:
        """Restore one output image payload under its snapshot UUID."""

        self._shell.workspace_restore_image_adapter.restore_output_image(
            workflow_id,
            reference,
            image,
            image_meta,
        )

    def project_restored_workflow(self, workflow_id: str) -> None:
        """Project one restored workflow route."""

        self._shell.restore_projection_controller.project_restored_workflow(workflow_id)

    def project_restored_settings(self) -> None:
        """Project the restored Settings route."""

        self._shell.restore_projection_controller.project_restored_settings()

    def apply_restored_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Apply restored shell layout facts after widgets exist."""

        self._shell.shell_layout_restore_controller.apply_restored_shell_layout(
            snapshot
        )


__all__ = ["ShellWorkspaceMaterializationPort"]
