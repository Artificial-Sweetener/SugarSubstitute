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

"""Warm restored workflow cube definitions before visible shell hydration."""

from __future__ import annotations

from typing import Any

from substitute.application.workspace_state import (
    RestoredCubeDefinitionWarmupResult,
    RestoredCubeDefinitionWarmupService,
    WorkspaceSnapshot,
)
from substitute.presentation.shell.main_window_startup_trace import (
    snapshot_trace_fields,
)
from substitute.shared.startup_trace import trace_mark


class ShellRestoreWarmupController:
    """Own restored workspace cube-definition warmup coordination."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose cube loader should warm restored definitions."""

        self._shell = shell

    def warm_restored_workspace_cube_definitions(
        self,
        initial_workspace: WorkspaceSnapshot | None,
    ) -> RestoredCubeDefinitionWarmupResult:
        """Warm restored cube definitions through the normal cube load service."""

        trace_mark(
            "main_window.warm_restored_workspace_cube_definitions.start",
            **snapshot_trace_fields(initial_workspace),
        )
        result = RestoredCubeDefinitionWarmupService().warm(
            initial_workspace,
            self._shell.cube_load_service,
        )
        trace_mark(
            "main_window.warm_restored_workspace_cube_definitions.end",
            requested_count=result.requested_count,
            warmed_count=result.warmed_count,
            skipped_count=result.skipped_count,
            failed_count=result.failed_count,
        )
        return result


__all__ = ["ShellRestoreWarmupController"]
