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

"""Adapt shell restore controllers to the workspace prehydration application port."""

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
    WorkspaceSnapshot,
)


class ShellWorkspacePrehydrationPort:
    """Expose only safe pre-show restore operations to prehydration."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that owns the composed restore collaborators."""

        self._shell = shell

    def begin_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Enter prehydration mode for one normalized workspace snapshot."""

        self._shell.shell_prehydrated_restore_controller.begin_prehydrated_restore(
            snapshot
        )

    def reset_restored_workspace(self) -> None:
        """Clear current workflow tabs and workflow-scoped widgets."""

        self._shell.restored_workflow_materializer.reset_restored_workspace()

    def add_prehydrated_workflow(
        self,
        snapshot: WorkflowSnapshot,
        *,
        activate: bool,
    ) -> None:
        """Create workflow session and tab chrome without editor projection."""

        self._shell.restored_workflow_materializer.add_prehydrated_workflow(
            snapshot,
            activate=activate,
        )

    def load_restored_input_image(self, path: Path) -> object | None:
        """Load one input image payload for restore."""

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
        """Load one output image payload for restore."""

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

    def remember_prehydrated_shell_layout(
        self,
        snapshot: ShellLayoutSnapshot | None,
    ) -> None:
        """Remember shell layout for visible finalization."""

        self._shell.shell_prehydrated_restore_controller.remember_prehydrated_shell_layout(
            snapshot
        )

    def finish_prehydrated_restore(self, snapshot: WorkspaceSnapshot) -> None:
        """Leave prehydration with enough state for visible finalization."""

        self._shell.shell_prehydrated_restore_controller.finish_prehydrated_restore(
            snapshot
        )


__all__ = ["ShellWorkspacePrehydrationPort"]
