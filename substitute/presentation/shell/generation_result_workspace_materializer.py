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

"""Append generation result workspaces into the shell."""

from __future__ import annotations

from typing import Any

from substitute.application.workspace_state import (
    WorkspaceMaterializationService,
    WorkspaceSnapshot,
)
from substitute.presentation.shell.shell_workspace_materialization_port import (
    ShellWorkspaceMaterializationPort,
)


class GenerationResultWorkspaceMaterializer:
    """Own generation-result workspace append orchestration for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell that supplies restore hydration and materialization ports."""

        self._shell = shell

    def materialize_generation_result_workspace(
        self,
        snapshot: WorkspaceSnapshot,
    ) -> tuple[str, ...]:
        """Append a generation result snapshot as restored workflow tabs."""

        append_snapshot = (
            self._shell.restored_workflow_materializer.snapshot_with_unique_open_ids(
                snapshot
            )
        )
        hydrated_snapshot = self._shell.workspace_restore_controller.hydrate_restored_workspace_snapshot(
            append_snapshot,
            operation="materialize_generation_result_workspace",
        )
        result = WorkspaceMaterializationService().materialize_into_existing_workspace(
            hydrated_snapshot,
            ShellWorkspaceMaterializationPort(self._shell),
        )
        return result.warnings


def generation_result_workspace_materializer_for(
    shell: Any,
) -> GenerationResultWorkspaceMaterializer:
    """Return the composed generation-result workspace materializer for a shell."""

    materializer = getattr(shell, "generation_result_workspace_materializer", None)
    if isinstance(materializer, GenerationResultWorkspaceMaterializer):
        return materializer
    materializer = GenerationResultWorkspaceMaterializer(shell)
    setattr(shell, "generation_result_workspace_materializer", materializer)
    return materializer


__all__ = [
    "GenerationResultWorkspaceMaterializer",
    "generation_result_workspace_materializer_for",
]
