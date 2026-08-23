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

"""Verify search and workflow-tab signal routing and autosave."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.presentation.shell import main_window_signal_binder as signal_binder_mod
from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)
from substitute.presentation.shell.session_autosave_coordinator import (
    SessionAutosaveRequestCategory,
)

from .support import _Signal


def test_search_signals_route_callbacks_and_allow_missing_closed_signal() -> None:
    """Search wiring should connect search events and tolerate optional close signals."""

    events: list[tuple[str, object]] = []
    workspace_search_actions = SimpleNamespace(
        on_context_search_changed=lambda context, text: events.append(
            ("changed", (context, text))
        ),
        on_cycle_search_match=lambda: events.append(("next", None)),
        on_cycle_search_match_backward=lambda: events.append(("previous", None)),
        on_search_closed=lambda: events.append(("closed", None)),
    )
    shell = SimpleNamespace(
        contextSearchBox=SimpleNamespace(
            contextSearchChanged=_Signal(),
            cycleSearchMatchRequested=_Signal(),
            cycleSearchMatchRequestedBackward=_Signal(),
            closed=_Signal(),
        ),
        workspace_search_actions=workspace_search_actions,
    )
    shell_without_closed = SimpleNamespace(
        contextSearchBox=SimpleNamespace(
            contextSearchChanged=_Signal(),
            cycleSearchMatchRequested=_Signal(),
            cycleSearchMatchRequestedBackward=_Signal(),
        ),
        workspace_search_actions=workspace_search_actions,
    )

    MainWindowSignalBinder(shell).connect_search_signals()
    MainWindowSignalBinder(shell_without_closed).connect_search_signals()
    shell.contextSearchBox.contextSearchChanged.fire("Node", "ksampler")
    shell.contextSearchBox.cycleSearchMatchRequested.fire()
    shell.contextSearchBox.cycleSearchMatchRequestedBackward.fire()
    shell.contextSearchBox.closed.fire()

    assert events == [
        ("changed", ("Node", "ksampler")),
        ("next", None),
        ("previous", None),
        ("closed", None),
    ]


def test_workflow_tab_signals_route_events_and_tab_structure_autosave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow-tab wiring should route actions and autosave tab structure changes."""

    events: list[tuple[str, object]] = []
    autosaves: list[SessionAutosaveRequestCategory] = []
    delegated: list[dict[str, object]] = []

    def reopen_latest_closed_workflow() -> bool:
        """Record a successful reopen request."""

        events.append(("reopen", None))
        return True

    def materialize_loaded_cube_input_canvas(
        view: object,
        workflow_id: str,
        cube_alias: str,
    ) -> None:
        """Record the materialization adapter call."""

        events.append(("materialize", (view, workflow_id, cube_alias)))

    def duplicate_workflow_tab_for_view(**kwargs: object) -> None:
        """Record direct duplicate-owner routing from signal binding."""

        delegated.append(kwargs)
        events.append(("duplicate", kwargs["workflow_id"]))

    monkeypatch.setattr(
        signal_binder_mod,
        "duplicate_workflow_tab_for_view",
        duplicate_workflow_tab_for_view,
    )
    monkeypatch.setattr(
        signal_binder_mod,
        "materialize_loaded_cube_input_canvas_for_view",
        materialize_loaded_cube_input_canvas,
    )
    workflow_duplicate_service = SimpleNamespace(name="duplicate-service")
    shell = SimpleNamespace(
        workflow_tabbar=SimpleNamespace(
            workflowRenameRequested=_Signal(),
            workflowAddRequested=_Signal(),
            workflowSelected=_Signal(),
            workflowCloseRequested=_Signal(),
            workflowDuplicateRequested=_Signal(),
            workflowReopenClosedRequested=_Signal(),
        ),
        workflow_workspace=SimpleNamespace(
            rename_workflow=lambda workflow_id, name: events.append(
                ("rename", (workflow_id, name))
            ),
            add_workflow=lambda: events.append(("add", None)),
            activate_workflow=lambda workflow_id, *, source: events.append(
                ("selected", (workflow_id, source))
            ),
            close_workflow=lambda workflow_id: events.append(("close", workflow_id)),
            reopen_latest_closed_workflow=reopen_latest_closed_workflow,
        ),
        workflow_duplicate_service=workflow_duplicate_service,
        session_autosave_controller=SimpleNamespace(
            request_categorized_session_autosave=autosaves.append,
            request_tab_selection_autosave=lambda: events.append(
                ("selection_autosave", None)
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_workflow_tab_signals()
    shell.workflow_tabbar.workflowRenameRequested.fire("wf-a", "New Name")
    shell.workflow_tabbar.workflowAddRequested.fire()
    shell.workflow_tabbar.workflowSelected.fire("wf-b")
    shell.workflow_tabbar.workflowCloseRequested.fire("wf-c")
    shell.workflow_tabbar.workflowDuplicateRequested.fire("wf-d")
    shell.workflow_tabbar.workflowReopenClosedRequested.fire()

    assert events == [
        ("rename", ("wf-a", "New Name")),
        ("add", None),
        ("selected", ("wf-b", "workflow_tab")),
        ("selection_autosave", None),
        ("close", "wf-c"),
        ("duplicate", "wf-d"),
        ("reopen", None),
    ]
    assert autosaves == [
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
        SessionAutosaveRequestCategory.TAB_STRUCTURE,
    ]
    assert delegated[0]["view"] is shell
    assert delegated[0]["workflow_workspace"] is shell.workflow_workspace
    assert delegated[0]["workflow_duplicate_service"] is workflow_duplicate_service
    assert delegated[0]["workflow_id"] == "wf-d"
    materialize = delegated[0]["materialize_loaded_cube_input_canvas"]
    assert callable(materialize)
    materialize("wf-copy", "CubeA")
    assert events[-1] == ("materialize", (shell, "wf-copy", "CubeA"))
    assert callable(delegated[0]["schedule_rehydration"])


def test_reopen_closed_workflow_autosaves_only_after_restore() -> None:
    """Reopen wiring should autosave only when a workflow is restored."""

    events: list[str] = []

    def reopen_successfully() -> bool:
        """Record a successful reopen request."""

        events.append("reopen")
        return True

    def skip_reopen() -> bool:
        """Record a reopen request that found no closed workflow."""

        events.append("reopen")
        return False

    shell = SimpleNamespace(
        workflow_workspace=SimpleNamespace(
            reopen_latest_closed_workflow=reopen_successfully,
        ),
        request_session_autosave=lambda: events.append("autosave"),
    )

    MainWindowSignalBinder(shell)._reopen_latest_closed_workflow()

    assert events == ["reopen", "autosave"]

    events.clear()
    shell.workflow_workspace = SimpleNamespace(
        reopen_latest_closed_workflow=skip_reopen,
    )

    MainWindowSignalBinder(shell)._reopen_latest_closed_workflow()

    assert events == ["reopen"]
