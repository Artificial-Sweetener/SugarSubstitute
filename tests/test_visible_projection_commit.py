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

"""Focused tests for visible projection commit behavior."""

from __future__ import annotations

import importlib
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
import substitute.presentation.editor.panel.visible_projection_commit as visible_projection_commit
from substitute.presentation.editor.panel.visible_projection_commit import (
    editor_panel_is_visible,
)
from tests.editor_projection_test_helpers import (
    _BuildSession,
    _FinalizingWidget,
    _Layout,
    _Signal,
    _TimerQueue,
    _Widget,
    _make_projection_handoff_panel,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)


def _patch_projection_timers(
    monkeypatch: pytest.MonkeyPatch,
    timer_queue: _TimerQueue,
) -> None:
    """Route hidden-build and visible-commit timers through one deterministic queue."""

    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )
    monkeypatch.setattr(
        cast(Any, getattr(visible_projection_commit, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )


def test_editor_panel_is_visible_accepts_missing_visibility_hook() -> None:
    """Panels without Qt visibility hooks should be considered publishable."""

    assert editor_panel_is_visible(SimpleNamespace()) is True


def test_editor_panel_is_visible_returns_false_after_deleted_qt_object() -> None:
    """Deleted Qt panels should fail closed during visible projection commits."""

    class _DeletedPanel:
        def isVisible(self) -> bool:  # noqa: N802
            """Raise like a deleted Qt object."""

            raise RuntimeError("wrapped C/C++ object has been deleted")

    assert editor_panel_is_visible(_DeletedPanel()) is False


def test_projection_coordinator_no_longer_defines_panel_visibility_wrapper() -> None:
    """Visible-commit panel visibility checks should live with commit ownership."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "_panel_is_visible" not in coordinator_methods


def test_finalize_pending_visible_projection_commits_background_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Returning to a workflow should reveal one completed background projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_projection_timers(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    completion_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[True])
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_projection_busy(message: str = "Loading") -> str:
        """Record projection busy start and return its token."""

        busy_calls.append(("begin", message))
        return "busy-token"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _workflow_overrides=lambda: {},
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _current_node_search_text=None,
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
        node_definition_gateway=object(),
        isVisible=lambda: workflow_session_service.active_workflow_id == "workflow-a",
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
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=_begin_projection_busy,
        _end_projection_busy=lambda token: busy_calls.append(("end", token)),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    cube_states = {"New": cube_new}

    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states=cube_states,
        stack_order=["New"],
        on_complete=lambda: completion_calls.append("complete"),
    )
    workflow_session_service.active_workflow_id = "workflow-b"
    timer_queue.run_all()

    assert coordinator.has_pending_visible_projection_commit()
    workflow_session_service.active_workflow_id = "workflow-a"

    assert coordinator.finalize_pending_visible_projection()

    assert not coordinator.has_pending_visible_projection_commit()
    assert panel.cube_widgets == {"New": new_widget}
    assert panel.cube_sections == {"New": new_widget}
    assert layout.added[-1] == ("widget", new_widget)
    assert new_widget.visible_changes == [False, True]
    assert new_widget.updates_enabled_changes == [False, True]
    assert registry_calls[-5:] == [
        "finalize:projected_reveal",
        "metrics_scheduled",
        "prompt_values",
        "links",
        "visibility",
    ]
    assert completion_calls == ["complete"]
    assert coordinator._composition.projection_state.clean_signature == (
        coordinator.current_projection_signature(
            workflow_id="workflow-a",
            cube_entries=[("New", cube_new)],
            cube_states=cube_states,
            stack_order=["New"],
        )
    )
    assert coordinator._composition.build_registry.record_for("New").state == "complete"
    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]


def test_active_hidden_panel_retries_pending_visible_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transiently hidden active panels should reveal after route visibility settles."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_projection_timers(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    completion_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    visible = {"current": False}
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[True])
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def begin_projection_busy(message: str = "Loading") -> str:
        """Record projection busy start and return its token."""

        busy_calls.append(("begin", message))
        return "busy-token"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _workflow_overrides=lambda: {},
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _current_node_search_text=None,
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
        node_definition_gateway=object(),
        isVisible=lambda: visible["current"],
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
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=begin_projection_busy,
        _end_projection_busy=lambda token: busy_calls.append(("end", token)),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    cube_states = {"New": cube_new}

    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states=cube_states,
        stack_order=["New"],
        on_complete=lambda: completion_calls.append("complete"),
    )
    timer_queue.run_next()
    timer_queue.run_next()

    assert coordinator.has_pending_visible_projection_commit()
    assert panel.cube_widgets == {}
    assert timer_queue.callbacks
    visible["current"] = True
    timer_queue.run_all()

    assert not coordinator.has_pending_visible_projection_commit()
    assert panel.cube_widgets == {"New": new_widget}
    assert completion_calls == ["complete"]
    assert coordinator._composition.projection_state.clean_signature == (
        coordinator.current_projection_signature(
            workflow_id="workflow-a",
            cube_entries=[("New", cube_new)],
            cube_states=cube_states,
            stack_order=["New"],
        )
    )
    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]


def test_attached_projection_completion_waits_for_visible_commit_after_deactivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow deactivation should defer callbacks attached to projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_projection_timers(monkeypatch, timer_queue)

    projected_widget = _Widget("projected")
    projected_session = _BuildSession(projected_widget, step_results=[True])
    build_sessions = [projected_session]
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
    )
    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("load"),
        completion_phase="complete",
    )
    workflow_session_service.active_workflow_id = "workflow-b"
    timer_queue.run_all()

    assert completed == []
    assert projected_session.step_calls == 1
    assert coordinator.has_pending_visible_projection_commit()
    assert coordinator._composition.active_sessions.active_session is not None

    workflow_session_service.active_workflow_id = "workflow-a"
    assert coordinator.finalize_pending_visible_projection()

    assert completed == ["load"]
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None


def test_superseded_insert_completion_waits_for_visible_commit_after_deactivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow deactivation should defer superseded insert completion callbacks."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_projection_timers(monkeypatch, timer_queue)

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
        """Return the next scripted build session for this cancellation flow."""

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
        _begin_projection_busy=lambda _message="Loading": "busy",
        _end_projection_busy=lambda _token: registry_calls.append("busy_end"),
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
    assert coordinator.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    workflow_session_service.active_workflow_id = "workflow-b"

    timer_queue.run_all()

    assert completed == []
    assert incremental_session.step_calls == 0
    assert projected_session.step_calls == 1
    assert coordinator.has_pending_visible_projection_commit()

    workflow_session_service.active_workflow_id = "workflow-a"
    assert coordinator.finalize_pending_visible_projection()

    assert completed == ["load"]
    assert (
        coordinator._composition.build_registry.record_for("Cube").state == "complete"
    )
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )


def test_superseded_insert_completion_resolves_once_across_repeated_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the projection that claims a superseded insert may resolve it."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_projection_timers(monkeypatch, timer_queue)

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
        """Return the next scripted build session for one new widget."""

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
    assert coordinator.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    timer_queue.run_all()
    coordinator.load_all_cubes(
        [("Cube", cube)],
        cube_states={"Cube": cube},
        stack_order=["Cube"],
    )
    timer_queue.run_all()

    assert completed == ["load"]
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
