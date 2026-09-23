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

"""Declare shell ports used by workflow activation and route projection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from substitute.application.workflows import (
    ClosedWorkflowBuffer,
    ClosedWorkflowSnapshotService,
    WorkflowSessionService,
)
from substitute.presentation.shell.workflow_surface_ports import (
    WorkflowSurfaceInvalidationPort,
)


class WorkflowTabItemProtocol(Protocol):
    """Describe the route identity exposed by a workflow tab item."""

    def routeKey(self) -> str:
        """Return the workflow route key."""


class WorkflowTabBarProtocol(Protocol):
    """Describe workflow-tab selection APIs used by route projection."""

    def currentIndex(self) -> int:
        """Return the selected tab index."""

    def tabItem(self, index: int) -> WorkflowTabItemProtocol:
        """Return the tab item at an index."""

    def select_workflow_tab(self, workflow_id: str, *, emit: bool = False) -> None:
        """Select a workflow tab without necessarily emitting user intent."""


class OverrideManagerProtocol(Protocol):
    """Describe outgoing override detachment during workflow activation."""

    def detach_override_widgets(self) -> None:
        """Detach live controls without destroying cached widgets."""


class WorkflowSurfaceRefreshSchedulerProtocol(Protocol):
    """Describe deferred workflow surface refresh scheduling."""

    def request(
        self,
        workflow_id: str,
        *,
        force_refresh: bool,
        reason: str,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        """Schedule refresh for one workflow route."""


class WorkflowSurfaceInvalidationProtocol(
    WorkflowSurfaceInvalidationPort,
    Protocol,
):
    """Extend projection invalidation with removed-workflow cleanup."""

    def remove_workflow(self, workflow_id: str) -> None:
        """Forget pending maintenance state for a closed workflow."""


class GenerationProgressProjectionProtocol(Protocol):
    """Describe progress projection owned by the generation action controller."""

    def project_active_workflow_progress(self) -> None:
        """Project selected workflow progress onto shell surfaces."""


class WorkflowWorkspaceView(Protocol):
    """Describe shell dependencies required for workflow route projection."""

    closed_workflow_buffer: ClosedWorkflowBuffer
    closed_workflow_snapshot_service: ClosedWorkflowSnapshotService
    workflow_session_service: WorkflowSessionService[object]
    workflow_tabbar: WorkflowTabBarProtocol
    generation_action_controller: GenerationProgressProjectionProtocol
    cube_stacks: dict[str, object]
    editor_panels: dict[str, object]
    override_managers: dict[str, OverrideManagerProtocol | None]


__all__ = [
    "WorkflowSurfaceInvalidationProtocol",
    "WorkflowSurfaceRefreshSchedulerProtocol",
    "WorkflowWorkspaceView",
]
