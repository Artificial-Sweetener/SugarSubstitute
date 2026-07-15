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

"""Build prompt-safe startup visibility summary fields."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.app.bootstrap.startup_restore_workspace import (
    restored_active_workflow_cube_count,
    restored_workspace_workflow_count,
)
from substitute.app.bootstrap.startup_timing import StartupTimer


@dataclass(frozen=True)
class StartupVisibleLoadingSummary:
    """Describe post-splash startup timing and restored workspace scale."""

    session_restore_used: bool
    workflow_count: int
    active_cube_count: int
    splash_close_to_shell_show_ms: str
    splash_close_to_hydration_complete_ms: str
    splash_close_to_restore_running_ms: str

    def log_fields(self) -> dict[str, object]:
        """Return structured logging fields for visible startup summary events."""

        return {
            "session_restore_used": self.session_restore_used,
            "workflow_count": self.workflow_count,
            "active_cube_count": self.active_cube_count,
            "splash_close_to_shell_show_ms": self.splash_close_to_shell_show_ms,
            "splash_close_to_hydration_complete_ms": (
                self.splash_close_to_hydration_complete_ms
            ),
            "splash_close_to_restore_running_ms": (
                self.splash_close_to_restore_running_ms
            ),
        }


def build_visible_loading_summary(
    *,
    startup_timer: StartupTimer,
    workspace: object | None,
) -> StartupVisibleLoadingSummary:
    """Build prompt-safe visible startup summary fields."""

    return StartupVisibleLoadingSummary(
        session_restore_used=workspace is not None,
        workflow_count=restored_workspace_workflow_count(workspace),
        active_cube_count=restored_active_workflow_cube_count(workspace),
        splash_close_to_shell_show_ms=_format_optional_elapsed(
            startup_timer.elapsed_ms_between("splash_closed", "main_shell_shown")
        ),
        splash_close_to_hydration_complete_ms=_format_optional_elapsed(
            startup_timer.elapsed_ms_between("splash_closed", "hydration_completed")
        ),
        splash_close_to_restore_running_ms=_format_optional_elapsed(
            startup_timer.elapsed_ms_between(
                "splash_closed",
                "restore_lifecycle_running",
            )
        ),
    )


def _format_optional_elapsed(elapsed_ms: float | None) -> str:
    """Return a stable log value for optional startup elapsed milliseconds."""

    return "" if elapsed_ms is None else f"{elapsed_ms:.3f}"


__all__ = [
    "StartupVisibleLoadingSummary",
    "build_visible_loading_summary",
]
