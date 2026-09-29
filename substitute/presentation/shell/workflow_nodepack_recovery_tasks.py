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

"""Own task routes and scopes for workflow nodepack recovery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitute.application.execution import TaskOutcome, TaskRequest, TaskScope
from substitute.presentation.shell.workflow_nodepack_recovery_execution import (
    WorkflowNodepackRecoveryRoute,
    WorkflowNodepackRecoveryRouteFactory,
)


@dataclass(slots=True)
class ActiveNodepackRecoveryTask:
    """Retain one execution route until its owner-thread callback settles."""

    scope: TaskScope
    route: WorkflowNodepackRecoveryRoute


class WorkflowNodepackRecoveryTasks:
    """Manage one controller's asynchronous package-maintenance task lifetimes."""

    def __init__(self, route_factory: WorkflowNodepackRecoveryRouteFactory) -> None:
        """Store the route factory and initialize the operation registry."""

        self._route_factory = route_factory
        self._request_id = 0
        self._active: list[ActiveNodepackRecoveryTask] = []

    def begin(self, workflow_id: str) -> tuple[ActiveNodepackRecoveryTask, int]:
        """Create and retain one package-maintenance task route."""

        self._request_id += 1
        request_id = self._request_id
        route = self._route_factory(
            request_id=request_id,
            target_workflow_id=workflow_id,
        )
        scope = TaskScope(
            submitter=route.submitter,
            scope_id=f"workflow_nodepack_recovery_{workflow_id}_{request_id}",
        )
        active = ActiveNodepackRecoveryTask(scope=scope, route=route)
        self._active.append(active)
        return active, request_id

    def submit(
        self,
        active: ActiveNodepackRecoveryTask,
        request: TaskRequest[object],
        receive: Callable[[TaskOutcome[object]], None],
    ) -> None:
        """Submit one operation and register its owner-thread completion."""

        try:
            handle = active.scope.submit(request)
            handle.add_done_callback(receive, reason="workflow_nodepack_recovery_done")
        except Exception:
            self.finish(active)
            raise

    def finish(self, active: ActiveNodepackRecoveryTask) -> None:
        """Release one completed or cancelled operation exactly once."""

        if active not in self._active:
            return
        active.scope.close(reason="workflow_nodepack_recovery_finished")
        active.route.close()
        self._active.remove(active)

    def close(self) -> None:
        """Release every outstanding task scope during shell teardown."""

        for active in tuple(self._active):
            self.finish(active)
