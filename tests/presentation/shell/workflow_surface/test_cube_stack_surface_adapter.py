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

"""Verify Cube Stack reconciliation from imported canonical workflow state."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.main_window_cube_stack_surface_adapter import (
    MainWindowCubeStackSurfaceAdapter,
)
from substitute.presentation.shell.workflow_surface_results import (
    ReconciliationToken,
    SurfaceRefreshStatus,
)
from tests.presentation.shell.workflow_surface.reconciler_fakes import (
    _PresentedCubeStack,
)
from tests.support.canonical_cube_graph import graph_backed_cube_workflow


class _IconFactory:
    """Return a deterministic non-warning Cube icon."""

    def icon_for_cube(self, **_kwargs: object) -> object:
        """Return one stable icon token."""

        return "cube-icon"


def test_imported_graph_rebuilds_stack_with_exact_model_parity() -> None:
    """A loaded native Cube graph should replace stale tabs from model truth."""

    workflow = graph_backed_cube_workflow("First", "Second")
    stack = _PresentedCubeStack()
    stack.insertTab(0, routeKey="Stale", text="Stale")
    shell = _shell(workflow, stack)

    result = MainWindowCubeStackSurfaceAdapter(shell).reconcile_cube_stack(
        "wf-a",
        ReconciliationToken(workflow_id="wf-a", generation=1),
    )

    assert result.status is SurfaceRefreshStatus.SUCCESS
    assert [stack.tabItem(index).routeKey() for index in range(stack.count())] == [
        "First",
        "Second",
    ]
    assert stack.current_index == 1
    assert shell.cube_stack is stack


def test_cube_stack_reconciliation_rejects_stale_workflow_token() -> None:
    """A late reconciliation must not mutate another active workflow's stack."""

    workflow = graph_backed_cube_workflow("First")
    stack = _PresentedCubeStack()
    stack.insertTab(0, routeKey="Unchanged", text="Unchanged")
    shell = _shell(workflow, stack)
    shell.workflow_session_service.active_workflow_id = "wf-b"

    result = MainWindowCubeStackSurfaceAdapter(shell).reconcile_cube_stack(
        "wf-a",
        ReconciliationToken(workflow_id="wf-a", generation=1),
    )

    assert result.status is SurfaceRefreshStatus.SKIPPED_STALE
    assert stack.count() == 1
    assert stack.tabItem(0).routeKey() == "Unchanged"


def _shell(workflow: object, stack: _PresentedCubeStack) -> SimpleNamespace:
    """Build the production adapter's narrow shell boundary."""

    return SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": workflow},
        ),
        cube_stacks={"wf-a": stack},
        cube_stack_container=SimpleNamespace(
            setCurrentWidget=lambda _widget: None,
        ),
        cube_stack=stack,
        cube_icon_factory=_IconFactory(),
        workflow_issue_state=None,
    )
