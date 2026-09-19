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

"""Reconcile Cube Stack presentation from authoritative workflow state."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import cast

from substitute.presentation.resources import cube_icon_resolver
from substitute.presentation.shell.cube_stack_presenter import (
    CubeStackPresenter,
    CubeStackProtocol,
)
from substitute.presentation.shell.workflow_surface_invalidation import WorkflowSurface
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshResult,
    SurfaceRefreshStatus,
    surface_result,
)
from substitute.presentation.shell.workflow_ui_factory import workflow_ui_factory_for
from substitute.shared.logging.logger import get_logger, log_debug, log_exception

_LOGGER = get_logger("presentation.shell.main_window_cube_stack_surface_adapter")


class MainWindowCubeStackSurfaceAdapter:
    """Project one workflow's Cube Stack without exposing shell internals."""

    def __init__(self, shell: object) -> None:
        """Store the shell that owns workflow-scoped stack widgets."""

        self._shell = shell

    def reconcile_cube_stack(
        self,
        workflow_id: str,
        token: ReconciliationToken,
    ) -> SurfaceRefreshResult:
        """Rebuild the active stack and verify exact model/presentation parity."""

        started_at = perf_counter()
        operation = "reconcile_cube_stack"
        if not self._is_current(workflow_id, token):
            return self._result(
                workflow_id,
                SurfaceRefreshStatus.SKIPPED_STALE,
                operation,
                started_at,
                cleanable=False,
            )
        session = getattr(self._shell, "workflow_session_service", None)
        workflows = getattr(session, "workflows", {})
        workflow = (
            workflows.get(workflow_id) if isinstance(workflows, Mapping) else None
        )
        if workflow is None:
            return self._result(
                workflow_id,
                SurfaceRefreshStatus.SKIPPED_MISSING,
                operation,
                started_at,
                cleanable=False,
                error="Workflow state is unavailable.",
            )
        try:
            existing_stack = getattr(self._shell, "cube_stacks", {}).get(workflow_id)
            active_alias = self._active_alias(existing_stack)
            cube_stack = workflow_ui_factory_for(
                self._shell
            ).reconcile_cube_stack_surface(workflow_id, set_as_current=True)
            stack_order = tuple(str(alias) for alias in workflow.stack_order)
            if cube_stack is None:
                if stack_order:
                    raise RuntimeError(
                        "Cube Stack is missing for a workflow that contains Cubes."
                    )
                return self._result(
                    workflow_id,
                    SurfaceRefreshStatus.SUCCESS,
                    operation,
                    started_at,
                )
            if active_alias not in stack_order:
                active_alias = stack_order[-1] if stack_order else None
            presentation = CubeStackPresenter(
                icon_resolver=cube_icon_resolver.CubeIconResolver(
                    cube_icon_factory=getattr(self._shell, "cube_icon_factory", None),
                )
            ).rebuild_stack(
                cast(CubeStackProtocol, cube_stack),
                workflow_id=workflow_id,
                workflow=workflow,
                active_cube_alias=active_alias,
                issue_state=getattr(self._shell, "workflow_issue_state", None),
            )
            presented_aliases = tuple(
                str(cube_stack.tabItem(index).routeKey())
                for index in range(cube_stack.count())
            )
            if (
                presentation.warnings
                or presentation.inserted_count != len(stack_order)
                or presented_aliases != stack_order
            ):
                raise RuntimeError(
                    "Cube Stack parity failed: "
                    f"model={stack_order!r}, presented={presented_aliases!r}, "
                    f"warnings={presentation.warnings!r}."
                )
            log_debug(
                _LOGGER,
                "Reconciled Cube Stack from workflow state",
                workflow_id=workflow_id,
                cube_count=len(stack_order),
                selected_alias=active_alias or "",
                presented_aliases=presented_aliases,
            )
            return self._result(
                workflow_id,
                SurfaceRefreshStatus.SUCCESS,
                operation,
                started_at,
            )
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Cube Stack reconciliation failed",
                workflow_id=workflow_id,
                operation=operation,
                error=error,
            )
            return self._result(
                workflow_id,
                SurfaceRefreshStatus.FAILED,
                operation,
                started_at,
                cleanable=False,
                error=str(error),
            )

    def _is_current(self, workflow_id: str, token: ReconciliationToken) -> bool:
        """Return whether the token still targets the active workflow."""

        session = getattr(self._shell, "workflow_session_service", None)
        return (
            token.workflow_id == workflow_id
            and getattr(session, "active_workflow_id", "") == workflow_id
        )

    @staticmethod
    def _active_alias(cube_stack: object | None) -> str | None:
        """Read the active route key before rebuilding an existing stack."""

        if cube_stack is None:
            return None
        current_index = getattr(cube_stack, "currentIndex", None)
        tab_item = getattr(cube_stack, "tabItem", None)
        if not callable(current_index) or not callable(tab_item):
            return None
        index = current_index()
        if not isinstance(index, int) or index < 0:
            return None
        item = tab_item(index)
        route_key = getattr(item, "routeKey", None)
        value = route_key() if callable(route_key) else None
        return str(value) if isinstance(value, str) and value else None

    @staticmethod
    def _result(
        workflow_id: str,
        status: SurfaceRefreshStatus,
        operation: str,
        started_at: float,
        *,
        cleanable: bool | None = None,
        error: str = "",
    ) -> SurfaceRefreshResult:
        """Build one timed Cube Stack reconciliation result."""

        return surface_result(
            workflow_id=workflow_id,
            surface=WorkflowSurface.CUBE_STACK,
            status=status,
            operation=operation,
            elapsed_ms=(perf_counter() - started_at) * 1000.0,
            cleanable=cleanable,
            error=error,
        )


__all__ = ["MainWindowCubeStackSurfaceAdapter"]
