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

"""Test completion transfer from incremental work to replacement projections."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
from typing import Any, cast
import pytest
import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _Layout,
    _Signal,
    _TimerQueue,
    _Widget,
    _make_projection_handoff_panel,
)


def test_superseded_insert_completion_transfers_to_replacement_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node-definition projection should complete a superseded cube-load insert."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    incremental_widget = _Widget("incremental")
    projected_widget = _Widget("projected")
    incremental_session = _BuildSession(
        incremental_widget,
        step_results=[False, True],
        first_usable_after=2,
    )
    projected_session = _BuildSession(projected_widget, step_results=[True])
    build_sessions = [incremental_session, projected_session]
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    registry_calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")

    def _begin_build_cube_widget(_alias: str, _state: object) -> _BuildSession:
        """Return the next scripted build session for this replacement flow."""

        return build_sessions.pop(0)

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states={},
        _stack_order=[],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: registry_calls.append(
            "discard"
        ),
        _begin_build_cube_widget=_begin_build_cube_widget,
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("load"),
    )
    assert completed == []

    assert coordinator.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )

    assert completed == []
    timer_queue.run_all()

    assert completed == ["load"]
    assert incremental_session.step_calls == 0
    assert projected_session.step_calls == 1
    assert panel.cube_widgets == {"Cube": projected_widget}
    assert (
        coordinator._composition.build_registry.record_for("Cube").state == "complete"
    )
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )


def test_stale_projection_claims_active_incremental_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full projection should finish an active insert it replaces as stale."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    incremental_widget = _Widget("incremental")
    projected_widget = _Widget("projected")
    incremental_session = _BuildSession(
        incremental_widget,
        step_results=[False, True],
        first_usable_after=2,
    )
    projected_session = _BuildSession(projected_widget, step_results=[True])
    build_sessions = [incremental_session, projected_session]
    registry_calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("load"),
        completion_phase="complete",
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    timer_queue.run_all()

    assert completed == ["load"]
    assert incremental_session.step_calls == 0
    assert projected_session.step_calls == 1
    assert "discard:incremental" in registry_calls
    assert panel.cube_widgets == {"Cube": projected_widget}
    assert (
        coordinator._composition.build_registry.record_for("Cube").state == "complete"
    )
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None


def test_batch_projection_claims_multiple_active_incremental_completions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full projection should resolve every active staged insert it replaces."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    inc_a_widget = _Widget("inc-a")
    inc_b_widget = _Widget("inc-b")
    proj_a_widget = _Widget("proj-a")
    proj_b_widget = _Widget("proj-b")
    proj_c_widget = _Widget("proj-c")
    inc_a_session = _BuildSession(inc_a_widget, step_results=[False, True])
    inc_b_session = _BuildSession(inc_b_widget, step_results=[False, True])
    proj_a_session = _BuildSession(proj_a_widget, step_results=[True])
    proj_b_session = _BuildSession(proj_b_widget, step_results=[True])
    proj_c_session = _BuildSession(proj_c_widget, step_results=[True])
    build_sessions = [
        inc_a_session,
        inc_b_session,
        proj_a_session,
        proj_b_session,
        proj_c_session,
    ]
    registry_calls: list[str] = []
    completed: list[str] = []
    cube_a = SimpleNamespace(buffer={"nodes": {}})
    cube_b = SimpleNamespace(buffer={"nodes": {}})
    cube_c = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "A",
        cube_a,
        cube_states={"A": cube_a},
        stack_order=["A"],
        on_complete=lambda: completed.append("A"),
        completion_phase="complete",
    )
    coordinator.insert_cube(
        "B",
        cube_b,
        cube_states={"A": cube_a, "B": cube_b, "C": cube_c},
        stack_order=["A", "B", "C"],
        on_complete=lambda: completed.append("B"),
        completion_phase="complete",
    )
    coordinator.load_all_cubes(
        [("A", cube_a), ("B", cube_b), ("C", cube_c)],
        cube_states={"A": cube_a, "B": cube_b, "C": cube_c},
        stack_order=["A", "B", "C"],
    )
    timer_queue.run_all()

    assert sorted(completed) == ["A", "B"]
    assert inc_a_session.step_calls == 0
    assert inc_b_session.step_calls == 0
    assert proj_a_session.step_calls == 1
    assert proj_b_session.step_calls == 1
    assert proj_c_session.step_calls == 1
    assert build_sessions == []
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None


def test_replacement_projection_transfers_claimed_incremental_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newer full projection should inherit callbacks owned by the prior projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    incremental_widget = _Widget("incremental")
    first_projected_widget = _Widget("projected-1")
    second_projected_widget = _Widget("projected-2")
    incremental_session = _BuildSession(incremental_widget, step_results=[False, True])
    first_projected_session = _BuildSession(first_projected_widget, step_results=[True])
    second_projected_session = _BuildSession(
        second_projected_widget,
        step_results=[True],
    )
    build_sessions = [
        incremental_session,
        first_projected_session,
        second_projected_session,
    ]
    registry_calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("load"),
        completion_phase="complete",
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    timer_queue.run_all()

    assert completed == ["load"]
    assert incremental_session.step_calls == 0
    assert first_projected_session.step_calls == 0
    assert second_projected_session.step_calls == 1
    assert panel.cube_widgets == {"Cube": second_projected_widget}
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None


def test_replacement_projection_transfers_full_projection_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newer full projection should inherit completion callbacks from prior projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    first_projected_widget = _Widget("projected-1")
    second_projected_widget = _Widget("projected-2")
    first_projected_session = _BuildSession(first_projected_widget, step_results=[True])
    second_projected_session = _BuildSession(
        second_projected_widget,
        step_results=[True],
    )
    build_sessions = [
        first_projected_session,
        second_projected_session,
    ]
    registry_calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=build_sessions,
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("restore"),
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    timer_queue.run_all()

    assert completed == ["restore"]
    assert first_projected_session.step_calls == 0
    assert second_projected_session.step_calls == 1
    assert first_projected_widget.parents == [None]
    assert first_projected_widget.deleted == 1
    assert second_projected_widget.parents == []
    assert second_projected_widget.deleted == 0
    assert panel.cube_widgets == {"Cube": second_projected_widget}
    assert coordinator._composition.active_sessions.active_session is None
