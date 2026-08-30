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

"""Test hidden full-projection cube builds and visible commit deferral."""

from __future__ import annotations

from __future__ import annotations
import importlib
import logging
from types import SimpleNamespace
import pytest
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _FinalizingWidget,
    _Layout,
    _Signal,
    _TimerQueue,
)

from tests.presentation.editor.panel.full_projection_load.hidden_build_support import (
    _patch_hidden_build_timer,
)


def test_load_all_cubes_defers_missing_widget_builds(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Full projection should use busy state while staged sections build."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, True])
    busy_calls: list[tuple[str, object]] = []
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_busy(message: str = "Loading") -> str:
        """Record one projection busy begin call."""

        busy_calls.append(("begin", message))
        return "busy-token"

    def _end_busy(token: object) -> None:
        """Record one projection busy end call."""

        busy_calls.append(("end", token))

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
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
        _begin_projection_busy=_begin_busy,
        _end_projection_busy=_end_busy,
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.full_projection_load_pipeline",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.projection_coordinator",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.rendering.render_reconciler",
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert layout.added == []
    assert build_session.step_calls == 0
    assert busy_calls == [("begin", "Loading")]
    assert new_widget.visible_changes == [False]
    assert new_widget.updates_enabled_changes == [False]
    assert registry_calls == [
        "reconcile",
        "snapshot",
        "sampler_scheduler",
    ]

    timer_queue.run_all()

    assert panel.cube_widgets == {"New": new_widget}
    assert panel.cube_sections == {"New": new_widget}
    assert layout.added[-1] == ("widget", new_widget)
    assert build_session.step_calls == 2
    assert new_widget.visible_changes == [False, True]
    assert new_widget.updates_enabled_changes == [False, True]
    assert new_widget.update_calls == 1
    assert registry_calls[-5:] == [
        "finalize:projected_reveal",
        "metrics_scheduled",
        "prompt_values",
        "links",
        "visibility",
    ]
    assert coordinator._composition.build_registry.record_for("New").state == "complete"
    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]
    assert "Started editor full projection cube load" in caplog.text
    assert "Began editor projection busy state" in caplog.text
    assert "Scheduled editor cube load reconciliation" in caplog.text
    assert "Revealed projected editor cube section" in caplog.text
    assert "Ended editor projection busy state" in caplog.text
    assert "Completed editor cube load reconciliation" in caplog.text
    assert "busy_started=True" in caplog.text


def test_load_all_cubes_continues_hidden_build_and_defers_visible_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inactive full projection should keep building without revealing hidden widgets."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    completion_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, True])
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
    timer_queue.run_next()
    workflow_session_service.active_workflow_id = "workflow-b"
    timer_queue.run_all()

    assert build_session.step_calls == 2
    assert coordinator.has_pending_visible_projection_commit()
    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert layout.added == []
    assert new_widget.visible_changes == [False]
    assert completion_calls == []
    assert coordinator._composition.projection_state.clean_signature is None
    assert busy_calls == [("begin", "Loading")]
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls
