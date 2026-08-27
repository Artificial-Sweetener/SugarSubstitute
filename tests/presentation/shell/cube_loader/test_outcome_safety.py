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

"""Test cube-loader outcome safety contracts."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from .execution_support import _QueuedSubmitter, _RejectingRouteFactory, _with_submitter
from .support import (
    _FakeQTimer,
    _FakeTabItem,
    _build_loader_state,
    _import_cube_loader_module,
    _stub_cube_service,
)


def test_load_cube_async_marks_placeholder_failed_when_service_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service load failures should mark placeholder as failed."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(
        _stub_cube_service(error=RuntimeError("no cube package"))
    )
    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (0, "Alias1 (Failed)", "", "Alias1 (Failed)")
    ]
    assert materialized == []


def test_load_cube_async_marks_placeholder_failed_when_cube_service_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing cube service wiring should fail closed and log the attribute failure."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()

    log_calls: list[tuple[str, dict[str, object]]] = []

    def _capture_log_error(_logger: object, message: str, **context: object) -> None:
        log_calls.append((message, context))

    monkeypatch.setattr(module, "log_error", _capture_log_error)

    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    module.load_cube_async(
        build_callbacks(SimpleNamespace()),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert materialized == []
    assert len(log_calls) == 1
    message, context = log_calls[0]
    assert message == "Failed to load cube"
    assert "load_cube_definition" in str(context["error"])


def test_load_cube_async_closes_runtime_route_when_definition_submit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected definition submission should fail the load and release its route."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    route_factory = _RejectingRouteFactory(fail_on_call=1)
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    callbacks = replace(
        build_callbacks(_stub_cube_service(graph={"nodes": {}})),
        cube_load_execution_route_factory=(
            lambda *, cube_load_trace_id: route_factory.route(module)
        ),
    )
    finished: list[str | None] = []

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=finished.append,
    )
    _FakeQTimer.run_all()

    assert route_factory.close_count == 1
    assert finished == [None]
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert materialized == []


def test_load_cube_async_closes_runtime_route_when_runtime_submit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rejected runtime-build submission should fail once and release its route."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    route_factory = _RejectingRouteFactory(fail_on_call=2)
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    callbacks = replace(
        build_callbacks(_stub_cube_service(graph={"nodes": {}})),
        cube_load_execution_route_factory=(
            lambda *, cube_load_trace_id: route_factory.route(module)
        ),
    )
    finished: list[str | None] = []

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=finished.append,
    )
    _FakeQTimer.run_all()

    assert route_factory.close_count == 1
    assert finished == [None]
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert materialized == []


def test_load_cube_async_marks_placeholder_failed_for_invalid_cube_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube-load service errors should mark placeholder failed without state mutation."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    invalid_wrapper_cube = {
        "cube_id": "wrapper_cube",
        "version": "1.0.0",
        "nodes": {
            "wrapper": {
                "class_type": "94f725d5-39bf-4060-be68-f573214a2055",
                "inputs": {"x": 1},
            }
        },
    }
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(
        _stub_cube_service(
            error=RuntimeError(f"contract invalid: {invalid_wrapper_cube['cube_id']}")
        )
    )
    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert materialized == []


def test_load_cube_async_marks_placeholder_failed_when_service_rejects_cube_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cube loader should fail closed when the load service rejects a cube id."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(
        _stub_cube_service(error=ValueError("Cube id '_archive\\old_cube' is invalid"))
    )
    module.load_cube_async(
        callbacks,
        cube_id="_archive\\old_cube",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1 (Failed)")]
    assert materialized == []


def test_load_cube_async_returns_early_when_captured_ui_targets_are_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If captured target stack/panel disappear before callback, loader should no-op."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    state.cube_stacks["wfA"].alive = False
    state.editor_panels["wfA"].alive = False
    submitter.run_next()
    submitter.run_next()
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == []
    assert materialized == []


def test_load_cube_async_resolves_placeholder_by_route_key_after_reorder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completion should update the current placeholder index, not the captured index."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    other_tab = _FakeTabItem("Other")
    placeholder_tab = state.cube_stacks["wfA"].items[0]
    state.cube_stacks["wfA"].items = [other_tab, placeholder_tab]
    state.cube_stacks["wfA"].itemMap = {
        "Other": other_tab,
        "loading:Alias1": placeholder_tab,
    }

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {}})),
            submitter,
        ),
        cube_id="Org/Base-Cubes/Base.cube",
        alias_name="Alias1",
        placeholder_index=1,
        buffer_patch=None,
    )

    state.cube_stacks["wfA"].items = [placeholder_tab, other_tab]
    submitter.run_next()
    submitter.run_next()
    _FakeQTimer.run_all()

    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (
            0,
            "Alias1",
            "v1.0.0 · base-cubes",
            '<div style="max-width: 420px; width: 420px; white-space: normal; '
            'word-wrap: break-word; overflow-wrap: anywhere;">'
            "<b>Org/Base-Cubes/Base.cube Display</b>, v1.0.0<br>"
            "Base-Cubes by Org</div>",
        )
    ]
    assert state.cube_stacks["wfA"].tab_icon_calls == [(0, "resolved-icon-token")]
    assert state.cube_icon_factory.calls == [
        ("Org/Base-Cubes/Base.cube", "Org/Base-Cubes/Base.cube Display", None)
    ]
    assert state.cube_stacks["wfA"].current_index_calls == [0]
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_ignores_completion_when_placeholder_was_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completion should not mutate workflow state after the placeholder disappears."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    state.cube_stacks["wfA"].items = []
    state.cube_stacks["wfA"].itemMap = {}
    submitter.run_next()
    submitter.run_next()
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    assert workflow.cubes == {}
    assert state.cube_stack_service.added == []
    assert state.cube_stacks["wfA"].tab_text_calls == []
    assert materialized == []
