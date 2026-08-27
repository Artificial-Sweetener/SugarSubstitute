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

"""Test full-projection handoff and stale staged-widget cleanup."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
from typing import Any, cast
import pytest
import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _TimerQueue,
    _Widget,
    _make_projection_handoff_panel,
)


def test_stale_full_projection_build_does_not_publish_after_session_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled staged full-projection builds must not reveal stale widgets."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    projected_widget = _Widget("projected")
    projected_session = _BuildSession(projected_widget, step_results=[True])
    registry_calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=[projected_session],
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("projection"),
    )
    active_session = coordinator._composition.active_sessions.active_session
    assert active_session is not None

    coordinator._composition.active_sessions.cancel(
        active_session,
        reason="test_stale_full_projection",
    )
    timer_queue.run_all()

    assert projected_session.step_calls == 0
    assert completed == []
    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert projected_widget.parents == [None]
    assert projected_widget.deleted == 1
    assert coordinator._composition.active_sessions.active_session is None
    record = coordinator._composition.build_registry.record_for("Cube")
    assert record is not None
    assert record.state == "cancelled"


def test_superseded_projection_discards_only_unrevealed_projected_widgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation should delete hidden batch builds that were not revealed."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    first_a_widget = _Widget("first-a")
    first_b_widget = _Widget("first-b")
    replacement_a_widget = _Widget("replacement-a")
    replacement_b_widget = _Widget("replacement-b")
    first_a_session = _BuildSession(first_a_widget, step_results=[True])
    first_b_session = _BuildSession(first_b_widget, step_results=[True])
    replacement_a_session = _BuildSession(replacement_a_widget, step_results=[True])
    replacement_b_session = _BuildSession(replacement_b_widget, step_results=[True])
    build_sessions = [
        first_a_session,
        first_b_session,
        replacement_a_session,
        replacement_b_session,
    ]
    registry_calls: list[str] = []
    cube_a = SimpleNamespace(buffer={"nodes": {}})
    cube_b = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("A", cube_a), ("B", cube_b)],
        cube_states={"A": cube_a, "B": cube_b},
        stack_order=["A", "B"],
    )
    timer_queue.run_next()
    coordinator.load_all_cubes(
        [("A", cube_a), ("B", cube_b)],
        cube_states={"A": cube_a, "B": cube_b},
        stack_order=["A", "B"],
    )
    timer_queue.run_all()

    assert first_a_session.step_calls == 1
    assert first_b_session.step_calls == 0
    assert replacement_a_session.step_calls == 1
    assert replacement_b_session.step_calls == 1
    assert first_a_widget.parents == [None]
    assert first_a_widget.deleted == 1
    assert first_b_widget.parents == [None]
    assert first_b_widget.deleted == 1
    assert replacement_a_widget.parents == []
    assert replacement_a_widget.deleted == 0
    assert replacement_b_widget.parents == []
    assert replacement_b_widget.deleted == 0
    assert panel.cube_widgets == {
        "A": replacement_a_widget,
        "B": replacement_b_widget,
    }
    assert coordinator._composition.active_sessions.active_session is None


def test_incremental_insert_attaches_to_active_full_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental insert should not start a competing build during projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    proj_a_widget = _Widget("proj-a")
    proj_b_widget = _Widget("proj-b")
    proj_a_session = _BuildSession(proj_a_widget, step_results=[True])
    proj_b_session = _BuildSession(proj_b_widget, step_results=[True])
    build_sessions = [proj_a_session, proj_b_session]
    registry_calls: list[str] = []
    completed: list[str] = []
    cube_a = SimpleNamespace(buffer={"nodes": {}})
    cube_b = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("A", cube_a), ("B", cube_b)],
        cube_states={"A": cube_a, "B": cube_b},
        stack_order=["A", "B"],
    )
    coordinator.insert_cube(
        "B",
        cube_b,
        cube_states={"A": cube_a, "B": cube_b},
        stack_order=["A", "B"],
        on_complete=lambda: completed.append("B"),
        completion_phase="complete",
    )

    assert build_sessions == []
    assert completed == []
    timer_queue.run_all()

    assert completed == ["B"]
    assert proj_a_session.step_calls == 1
    assert proj_b_session.step_calls == 1
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None
