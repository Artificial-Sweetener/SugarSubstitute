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

"""Test incremental-insert replacement, cancellation, and alias isolation."""

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
