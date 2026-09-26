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

"""Trace a workflow switch while production editor construction is in flight."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)

from .fixtures import read_json, workflow_fixture_path
from .production_fixture import workflow_from_fixture
from .production_mount import build_editor_panel, build_trace_shell
from .production_signatures import parent_chain_violations
from .qt_harness import create_hidden_host, drain_qt_events, drain_until
from .scenarios import WorkflowScenario
from .trace_events import ProjectionTraceRecorder


def trace_inflight_workflow_switch(
    scenarios: Sequence[WorkflowScenario],
    *,
    fixtures_dir: Path,
    settle_turns: int,
) -> dict[str, Any] | None:
    """Switch to a second production panel before the first build can settle."""

    if len(scenarios) < 2:
        return None
    first_scenario, second_scenario = scenarios[:2]
    first_fixture = read_json(
        workflow_fixture_path(fixtures_dir, first_scenario.workflow_id)
    )
    second_fixture = read_json(
        workflow_fixture_path(fixtures_dir, second_scenario.workflow_id)
    )
    first_workflow, first_definitions = workflow_from_fixture(first_fixture)
    second_workflow, second_definitions = workflow_from_fixture(second_fixture)
    first_host = create_hidden_host(show_window=True)
    second_host = create_hidden_host(show_window=True)
    first_panel = build_editor_panel(
        host=first_host,
        workflow_id=first_scenario.workflow_id,
        definitions=first_definitions,
    )
    second_panel = build_editor_panel(
        host=second_host,
        workflow_id=second_scenario.workflow_id,
        definitions=second_definitions,
    )
    trace_shell = build_trace_shell(
        workflow_id=first_scenario.workflow_id,
        workflow=first_workflow,
        panel=first_panel,
        recorder=ProjectionTraceRecorder(),
    )
    shell = trace_shell.shell
    shell.workflow_session_service.workflows = {
        first_scenario.workflow_id: first_workflow,
        second_scenario.workflow_id: second_workflow,
    }
    shell.editor_panels = {
        first_scenario.workflow_id: first_panel,
        second_scenario.workflow_id: second_panel,
    }
    shell.get_active_workflow = lambda: shell.workflow_session_service.workflows.get(
        shell.workflow_session_service.active_workflow_id
    )
    shell.editor_panel_container.currentWidget = lambda: shell.active_editor_panel
    first_panel.mainwindow = shell
    second_panel.mainwindow = shell
    first_completions = 0
    second_completions = 0

    def first_complete(_result: object) -> None:
        """Count stale first-workflow completion publication."""

        nonlocal first_completions
        first_completions += 1

    def second_complete(_result: object) -> None:
        """Count active second-workflow completion publication."""

        nonlocal second_completions
        second_completions += 1

    try:
        first_result = MainWindowEditorSurfaceAdapter(shell).refresh_editor_surface(
            first_scenario.workflow_id,
            force=False,
            on_complete=first_complete,
        )
        shell.workflow_session_service.active_workflow_id = second_scenario.workflow_id
        shell._active_workspace_route = second_scenario.workflow_id
        shell.active_editor_panel = second_panel
        second_result = MainWindowEditorSurfaceAdapter(shell).refresh_editor_surface(
            second_scenario.workflow_id,
            force=False,
            on_complete=second_complete,
        )
        if first_result.error or second_result.error:
            raise RuntimeError(first_result.error or second_result.error)
        drain_until(lambda: second_completions == 1, max_turns=settle_turns)
        drain_qt_events(50)
        second_violations = parent_chain_violations(second_panel)
        passed = (
            first_completions == 0 and second_completions == 1 and not second_violations
        )
        return {
            "from_scenario_id": first_scenario.workflow_id,
            "to_scenario_id": second_scenario.workflow_id,
            "first_completion_count_while_inactive": first_completions,
            "second_completion_count": second_completions,
            "first_projection_active": first_panel.is_projection_active(),
            "first_pending_visible_commit": (
                first_panel.has_pending_visible_projection_commit()
            ),
            "second_parent_chain_violations": second_violations,
            "passed": passed,
        }
    finally:
        first_host.close()
        second_host.close()
        first_host.deleteLater()
        second_host.deleteLater()
        drain_qt_events(25)
