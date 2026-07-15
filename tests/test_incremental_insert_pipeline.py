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

"""Focused tests for incremental insert pipeline behavior."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.editor_projection_test_helpers import (
    _BuildSession,
    _FinalizingWidget,
    _Layout,
    _LayoutItem,
    _Signal,
    _TimerQueue,
    _Widget,
    _make_projection_handoff_panel,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "incremental_insert_pipeline.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_insert_cube_builds_new_widget_and_repopulates_layout_in_stack_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental cube insert should keep physical layout aligned to stack order."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, callback: callback()),
    )

    existing_widget = _Widget()
    new_widget = _Widget()
    layout = _Layout([_LayoutItem(widget=existing_widget)])
    built_aliases: list[str] = []
    scroll_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scroll_signal, value=lambda: 3)
    registry_calls: list[str] = []
    refresh_kwargs: list[dict[str, object]] = []

    cube_existing = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_build_cube_widget(alias: str, _state: object) -> _BuildSession:
        built_aliases.append(alias)
        return _BuildSession(new_widget)

    def _record_visibility(**kwargs: object) -> None:
        registry_calls.append("visibility")
        refresh_kwargs.append(kwargs)

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Existing": existing_widget},
        cube_sections={"Existing": existing_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states={"Existing": cube_existing},
        _stack_order=["Existing"],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=_begin_build_cube_widget,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        begin_projection_prompt_context=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("incremental insert should not start prompt context")
        ),
        clear_projection_prompt_context=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("incremental insert should not clear prompt context")
        ),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=_record_visibility,
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"Existing": cube_existing, "New": cube_new},
        stack_order=["Existing", "New"],
    )

    assert built_aliases == ["New"]
    assert existing_widget.parents == [None]
    assert panel.cube_widgets == {"Existing": existing_widget, "New": new_widget}
    assert panel.cube_sections["New"] is new_widget
    assert layout.added == [
        ("spacing", 8),
        ("widget", existing_widget),
        ("spacing", 8),
        ("widget", new_widget),
    ]
    assert registry_calls == [
        "hydrate",
        "reconcile",
        "snapshot",
        "sampler_scheduler",
        "scroll",
        "prompt_values:New",
        "links:New",
        "visibility",
    ]
    assert refresh_kwargs == [{"reason": "cube_added", "use_cached_snapshot": True}]


def test_insert_cube_honors_reordered_placeholder_stack_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental insert should place the completed cube at its stack-order slot."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, callback: callback()),
    )

    existing_widget = _Widget()
    new_widget = _Widget()
    layout = _Layout([_LayoutItem(widget=existing_widget)])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 5)
    registry_calls: list[str] = []

    cube_existing = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Existing": existing_widget},
        cube_sections={"Existing": existing_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states={"Existing": cube_existing},
        _stack_order=["Existing"],
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: _BuildSession(new_widget),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"Existing": cube_existing, "New": cube_new},
        stack_order=["New", "Existing"],
    )

    assert layout.added == [
        ("spacing", 8),
        ("widget", new_widget),
        ("spacing", 8),
        ("widget", existing_widget),
    ]
    assert list(panel.cube_sections) == ["New", "Existing"]


def test_stale_incremental_insert_washes_replacement_until_first_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updated cube sections should hide staged rebuild churn behind a local wash."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    existing_widget = _Widget("existing")
    replacement_widget = _Widget("replacement")
    replacement_session = _BuildSession(
        replacement_widget,
        step_results=[False, True],
        first_usable_after=2,
    )
    registry_calls: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})
    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = _make_projection_handoff_panel(
        build_sessions=[replacement_session],
        registry_calls=registry_calls,
        workflow_session_service=workflow_session_service,
    )
    panel.cube_widgets = {"Cube": existing_widget}
    panel.cube_sections = {"Cube": existing_widget}
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.mark_cube_sections_stale(["Cube"], reason="cube_definition_changed")
    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        completion_phase="complete",
    )

    assert replacement_widget.update_wash_calls == [("show", "Updating")]
    timer_queue.run_next()
    assert replacement_widget.update_wash_calls == [("show", "Updating")]
    timer_queue.run_next()
    assert replacement_widget.update_wash_calls == [
        ("show", "Updating"),
        ("hide", ""),
    ]
    assert panel.cube_widgets == {"Cube": replacement_widget}


def test_insert_cube_adds_silent_batch_insert_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silent incremental inserts should add the cube directly to the layout."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(lambda _msec, callback: callback()),
    )

    new_widget = _Widget()
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    registry_calls: list[str] = []
    cube_new = SimpleNamespace(buffer={"nodes": {}})

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
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: _BuildSession(new_widget),
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    assert layout.added == [("spacing", 8), ("widget", new_widget)]


def test_insert_cube_allows_concurrent_builds_for_different_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different cube aliases should not cancel each other's build sessions."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    widget_a = _Widget("a")
    widget_b = _Widget("b")
    sessions = {
        "CubeA": _BuildSession(widget_a, step_results=[True]),
        "CubeB": _BuildSession(widget_b, step_results=[True]),
    }
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    registry_calls: list[str] = []
    completed: list[str] = []

    def _begin_build(alias: str, _state: object) -> _BuildSession:
        """Return the scripted build session for one alias."""

        return sessions[alias]

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
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _begin_build_cube_widget=_begin_build,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "CubeA",
        SimpleNamespace(buffer={"nodes": {}}),
        cube_states={"CubeA": object()},
        stack_order=["CubeA"],
        on_complete=lambda: completed.append("CubeA"),
    )
    coordinator.insert_cube(
        "CubeB",
        SimpleNamespace(buffer={"nodes": {}}),
        cube_states={"CubeA": object(), "CubeB": object()},
        stack_order=["CubeA", "CubeB"],
        on_complete=lambda: completed.append("CubeB"),
    )

    timer_queue.run_all()

    assert completed == ["CubeA", "CubeB"]
    assert sessions["CubeA"].step_calls == 1
    assert sessions["CubeB"].step_calls == 1
    assert (
        coordinator._composition.build_registry.record_for("CubeA").state == "complete"
    )
    assert (
        coordinator._composition.build_registry.record_for("CubeB").state == "complete"
    )


def test_insert_cube_same_alias_supersedes_only_stale_same_alias_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A newer insert for one alias should cancel only that alias's stale session."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    widget = _Widget("same")
    session = _BuildSession(widget, step_results=[True])
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    registry_calls: list[str] = []
    completed: list[str] = []
    transaction_calls: list[str] = []

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
        node_definition_gateway=object(),
        begin_behavior_refresh_transaction=lambda *, reason: transaction_calls.append(
            f"begin:{reason}"
        ),
        end_behavior_refresh_transaction=lambda *, reason: transaction_calls.append(
            f"end:{reason}"
        ),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _begin_build_cube_widget=lambda _alias, _state: session,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "CubeA",
        SimpleNamespace(buffer={"nodes": {}}),
        cube_states={"CubeA": object()},
        stack_order=["CubeA"],
        on_complete=lambda: completed.append("first"),
    )
    coordinator.insert_cube(
        "CubeA",
        SimpleNamespace(buffer={"nodes": {}}),
        cube_states={"CubeA": object()},
        stack_order=["CubeA"],
        on_complete=lambda: completed.append("second"),
    )

    timer_queue.run_all()

    assert completed == ["second"]
    assert session.step_calls == 1
    assert (
        coordinator._composition.build_registry.record_for("CubeA").state == "complete"
    )
    assert transaction_calls.count("end:cube_added") == 2


def test_insert_cube_reports_first_usable_before_progressive_build_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental cube insert should notify callers at first-usable state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    existing_widget = _Widget()
    layout = _Layout([_LayoutItem(widget=existing_widget)])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 5)
    registry_calls: list[str] = []
    new_widget = _FinalizingWidget("new", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, False, True])
    completed: list[str] = []

    cube_existing = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Existing": existing_widget},
        cube_sections={"Existing": existing_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states={"Existing": cube_existing},
        _stack_order=["Existing"],
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    coordinator.insert_cube(
        "New",
        cube_new,
        cube_states={"Existing": cube_existing, "New": cube_new},
        stack_order=["Existing", "New"],
        on_complete=lambda: completed.append("done"),
    )

    assert build_session.step_calls == 0
    assert completed == []
    assert registry_calls == [
        "hydrate",
        "reconcile",
        "snapshot",
        "sampler_scheduler",
        "scroll",
    ]

    timer_queue.run_next()
    assert build_session.step_calls == 1
    assert completed == ["done"]
    assert "prompt_values:New" not in registry_calls
    assert registry_calls[-2:] == [
        "finalize:incremental_first_usable",
        "metrics_scheduled",
    ]

    timer_queue.run_next()
    assert build_session.step_calls == 2
    assert completed == ["done"]

    timer_queue.run_next()
    assert build_session.step_calls == 3
    assert completed == ["done"]
    assert registry_calls[-5:] == [
        "prompt_values:New",
        "links:New",
        "visibility",
        "finalize:incremental_complete",
        "metrics_scheduled",
    ]
    assert coordinator._composition.build_registry.record_for("New").state == "complete"
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )


def test_insert_cube_can_report_completion_after_progressive_build_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staged batch inserts can wait for final geometry before reporting complete."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 5)
    registry_calls: list[str] = []
    new_widget = _FinalizingWidget("new", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, False, True])
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states={},
        _stack_order=[],
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _build_cube_widget=lambda _alias, _state: new_widget,
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        hydrate_node_definitions_for_projection=lambda **_kwargs: registry_calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )

    mod.EditorPanelProjectionCoordinator(panel).insert_cube(
        "New",
        cube_new,
        cube_states={"New": cube_new},
        stack_order=["New"],
        on_complete=lambda: registry_calls.append("complete_cb"),
        completion_phase="complete",
    )

    timer_queue.run_next()
    assert build_session.step_calls == 1
    assert "complete_cb" not in registry_calls

    timer_queue.run_next()
    assert build_session.step_calls == 2
    assert "complete_cb" not in registry_calls

    timer_queue.run_next()
    assert build_session.step_calls == 3
    assert registry_calls[-3:] == [
        "finalize:incremental_complete",
        "metrics_scheduled",
        "complete_cb",
    ]


def test_stale_active_insert_build_is_not_treated_as_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Node-definition invalidation should cancel a partial inserted section."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    monkeypatch.setattr(
        cast(Any, getattr(hidden_build_scheduler, "QTimer")),
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )

    widget = _Widget("partial")
    build_session = _BuildSession(widget, step_results=[True])
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    calls: list[str] = []
    completed: list[str] = []
    cube = SimpleNamespace(buffer={"nodes": {}})

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
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_for_cube=lambda alias: calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: calls.append(f"links:{alias}"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: calls.append("snapshot"),
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.insert_cube(
        "Cube",
        cube,
        cube_states={"Cube": cube},
        stack_order=["Cube"],
        on_complete=lambda: completed.append("done"),
    )

    assert coordinator.mark_cube_sections_stale(
        ["Cube"],
        reason="node_definition_changed",
    )
    timer_queue.run_all()

    assert build_session.step_calls == 0
    assert completed == []
    assert (
        coordinator._composition.build_registry.record_for("Cube").state == "cancelled"
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


def test_incremental_insert_pipeline_does_not_import_coordinator_or_fluent() -> None:
    """Incremental insert orchestration should stay out of the coordinator monolith."""

    imports = _imported_module_names(PIPELINE_SOURCE)
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )
    assert "_coordinator" not in source
    assert "EditorIncrementalInsertPorts(" in (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "editor"
        / "panel"
        / "projection_composition.py"
    ).read_text(encoding="utf-8")


def test_projection_coordinator_no_longer_defines_incremental_insert_pipeline() -> None:
    """Moved incremental insert methods should not return to the coordinator."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    coordinator_imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    composition_imported_names = {
        alias.name
        for node in ast.walk(ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "EditorHiddenBuildAndInsertPipeline" not in class_methods
    assert "EditorIncrementalInsertPipeline" not in coordinator_imported_names
    assert "EditorIncrementalInsertPipeline" in composition_imported_names
    assert "_log_insert_started" not in coordinator_methods
    assert "_prepare_incremental_insert_plan" not in coordinator_methods
    assert "_repopulate_incremental_insert_layout" not in coordinator_methods
    assert "_report_insert_complete" not in coordinator_methods
    assert "_finish_insert_first_usable" not in coordinator_methods
    assert "_finish_insert" not in coordinator_methods
    assert "_cancel_incremental_insert" not in coordinator_methods
