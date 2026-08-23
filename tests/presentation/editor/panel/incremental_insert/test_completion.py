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

"""Test incremental-insert first-usable and terminal completion publication."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
from typing import Any, cast
import pytest
import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _FinalizingWidget,
    _Layout,
    _LayoutItem,
    _Signal,
    _TimerQueue,
    _Widget,
)


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
