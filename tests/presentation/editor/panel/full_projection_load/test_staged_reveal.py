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

"""Test staged full-projection reveal, finalization, and failure cleanup."""

from __future__ import annotations

from __future__ import annotations
import importlib
import logging
from types import SimpleNamespace
import pytest
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from tests.presentation.editor.panel.projection_support import (
    _BuildSession,
    _FailingAddLayout,
    _FinalizingWidget,
    _Layout,
    _Signal,
    _TimerQueue,
    _Widget,
)

from tests.presentation.editor.panel.full_projection_load.hidden_build_support import (
    _patch_hidden_build_timer,
)


def test_load_all_cubes_ends_busy_when_staged_reveal_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Busy state should be released when a staged reveal hits an expected failure."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    new_widget = _Widget("built")
    build_session = _BuildSession(new_widget, step_results=[True])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
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
        _layout=_FailingAddLayout([]),
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
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
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.full_projection_load_pipeline",
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_coordinator",
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    timer_queue.run_all()

    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls
    assert coordinator._composition.build_registry.record_for("New").state == "failed"
    assert "Failed editor visible projection commit" in caplog.text
    assert "Ended editor projection busy state" in caplog.text


def test_load_all_cubes_does_not_complete_when_staged_finalization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projected builds should remain non-complete when reveal finalization fails."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    registry_calls: list[str] = []
    new_widget = _FinalizingWidget(
        "built",
        registry_calls,
        fail_on_finalize=True,
    )
    build_session = _BuildSession(new_widget, step_results=[True])
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    cube_new = SimpleNamespace(buffer={"nodes": {}})
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
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=lambda _message="Loading": "busy-token",
        _end_projection_busy=lambda _token: registry_calls.append("busy_end"),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )
    timer_queue.run_all()

    assert "finalize:projected_reveal" in registry_calls
    assert "metrics_now" not in registry_calls
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls
    assert registry_calls[-1] == "busy_end"
    assert coordinator._composition.build_registry.record_for("New").state == "failed"


def test_projected_cube_builds_reveal_once_after_all_sections_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full projection should batch staged reveals into one layout commit."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = SimpleNamespace(
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    widget_a = _Widget("A")
    widget_b = _Widget("B")
    session_a = _BuildSession(widget_a, step_results=[False, True])
    session_b = _BuildSession(widget_b, step_results=[True])
    token_a = coordinator._composition.build_registry.start(
        alias="A",
        widget=widget_a,
        session=session_a,
        snapshot_identity=None,
        definition_identity=None,
    )
    token_b = coordinator._composition.build_registry.start(
        alias="B",
        widget=widget_b,
        session=session_b,
        snapshot_identity=None,
        definition_identity=None,
    )
    projected_builds = [
        ProjectedCubeBuild(
            cube_alias="A",
            final_widget=widget_a,
            build_session=session_a,
            started_at=0.0,
            token=token_a,
        ),
        ProjectedCubeBuild(
            cube_alias="B",
            final_widget=widget_b,
            build_session=session_b,
            started_at=0.0,
            token=token_b,
        ),
    ]
    revealed_batches: list[tuple[str, ...]] = []
    completions: list[str] = []
    cancellations: list[str] = []

    def reveal_batch(
        builds: list[object],
        *,
        workflow_id: str,
    ) -> None:
        """Record the exact reveal batch requested by the scheduler."""

        revealed_batches.append(
            tuple(getattr(build, "cube_alias") for build in builds) + (workflow_id,)
        )

    monkeypatch.setattr(
        coordinator._composition.render_reconciler,
        "reveal_projected_cube_builds",
        reveal_batch,
    )
    monkeypatch.setattr(
        coordinator._composition.render_reconciler,
        "reveal_projected_cube_build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("single reveal path should not run")
        ),
    )

    coordinator._composition.hidden_build_scheduler.schedule_projected_cube_builds(
        projected_builds,
        on_complete=lambda: completions.append("complete"),
        on_cancel=lambda: cancellations.append("cancel"),
        workflow_id="workflow-a",
        is_current=lambda: True,
    )
    timer_queue.run_all()

    assert revealed_batches == [("A", "B", "workflow-a")]
    assert completions == ["complete"]
    assert cancellations == []
    assert coordinator._composition.build_registry.record_for("A").state == "complete"
    assert coordinator._composition.build_registry.record_for("B").state == "complete"
