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

"""Characterization tests for async cube loading orchestration."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import replace
from types import SimpleNamespace

from substitute.application.execution import CancellationToken, TaskRequest
from tests.execution_testing import (
    ImmediateTaskSubmitter,
    ManualTaskHandle,
)


class _QueuedSubmitter:
    """Queue execution requests until tests run them manually."""

    def __init__(self) -> None:
        """Create an empty execution queue."""

        self.items: list[
            tuple[TaskRequest[object], CancellationToken, ManualTaskHandle[object]]
        ] = []

    def submit(
        self,
        request: TaskRequest[object],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[object]:
        """Record one execution request without running it."""

        handle: ManualTaskHandle[object] = ManualTaskHandle(request)
        self.items.append((request, cancellation, handle))
        return handle

    def run_next(self) -> None:
        """Run the next queued request and publish its result."""

        request, cancellation, handle = self.items.pop(0)
        handle.complete_success(request.work(cancellation))


class _RejectingRouteFactory:
    """Create cube-load routes that reject one selected submit call."""

    def __init__(self, *, fail_on_call: int) -> None:
        """Create a route factory whose submitter fails on one call number."""

        self.submitter_instance = _RejectingRuntimeSubmitter(
            fail_on_call=fail_on_call,
            close_callback=self._record_close,
        )
        self.close_count = 0

    def route(self, module):
        """Return a route through the module's public route value."""

        return module.CubeLoadExecutionRoute(
            submitter=self.submitter_instance,
            close=self.submitter_instance.close,
        )

    def _record_close(self) -> None:
        """Record one owner-route close."""

        self.close_count += 1


class _RejectingRuntimeSubmitter:
    """Run immediate tasks until one configured submission is rejected."""

    def __init__(
        self,
        *,
        fail_on_call: int,
        close_callback: Callable[[], None],
    ) -> None:
        """Store failure and close behavior."""

        self._fail_on_call = fail_on_call
        self._close_callback = close_callback
        self._immediate = ImmediateTaskSubmitter()
        self._submit_count = 0
        self._closed = False

    def submit(
        self,
        request: TaskRequest[object],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[object]:
        """Submit immediately unless this call is configured to fail."""

        self._submit_count += 1
        if self._submit_count == self._fail_on_call:
            raise RuntimeError("execution lane rejected test task")
        return self._immediate.submit(request, cancellation=cancellation)

    def close(self) -> None:
        """Record close once."""

        if self._closed:
            return
        self._closed = True
        self._close_callback()


def _route_factory(module, submitter, close: Callable[[], None] | None = None):
    """Return a cube-load route factory for one test submitter."""

    def _factory(*, cube_load_trace_id: str):
        """Create a route for one cube-load request."""

        _ = cube_load_trace_id
        return module.CubeLoadExecutionRoute(
            submitter=submitter,
            close=close or (lambda: None),
        )

    return _factory


def _with_submitter(module, callbacks, submitter: _QueuedSubmitter):
    """Return callbacks that use the queued test submitter."""

    return replace(
        callbacks,
        cube_load_execution_route_factory=_route_factory(module, submitter),
    )


def _import_cube_loader_module(monkeypatch):
    """Import cube loader and replace async Qt schedulers for deterministic tests."""

    class _QCoreApplication:
        """Deliver cube-loader completion events synchronously."""

        @staticmethod
        def postEvent(receiver, event):
            """Invoke the result callback directly."""

            event.callback(event.result)

    module = importlib.import_module("substitute.presentation.shell.cube_loader")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "QCoreApplication", _QCoreApplication, raising=False)
    monkeypatch.setattr(
        module,
        "QTimer",
        type(
            "QTimer",
            (),
            {"singleShot": staticmethod(lambda _msec, callback: callback())},
        ),
    )
    return module


class _FakeQTimer:
    """Queueing timer shim to control callback ordering in tests."""

    queue: list[Callable[[], None]] = []

    @staticmethod
    def clear() -> None:
        _FakeQTimer.queue.clear()

    @staticmethod
    def singleShot(_msec, callback) -> None:
        _FakeQTimer.queue.append(callback)

    @staticmethod
    def run_all() -> None:
        while _FakeQTimer.queue:
            callback = _FakeQTimer.queue.pop(0)
            callback()

    @staticmethod
    def run_next() -> None:
        """Run one queued timer callback."""

        callback = _FakeQTimer.queue.pop(0)
        callback()


class _FakeTabItem:
    """Simple cube tab item carrying only route key state."""

    def __init__(self, key: str) -> None:
        self._key = key

    def routeKey(self) -> str:
        return self._key

    def setRouteKey(self, key: str) -> None:
        self._key = key


class _FakeCubeStack:
    """Small stack double that mimics the subset used by load_cube_async."""

    def __init__(self, initial_key: str) -> None:
        self.items = [_FakeTabItem(initial_key)]
        self.itemMap = {initial_key: self.items[0]}
        self.tab_text_calls: list[tuple[int, str]] = []
        self.tab_presentation_calls: list[tuple[int, str, str, str]] = []
        self.tab_icon_calls: list[tuple[int, object]] = []
        self.current_index_calls: list[int] = []
        self.alive = True

    def __bool__(self) -> bool:
        return self.alive

    def setTabText(self, index: int, text: str) -> None:
        self.tab_text_calls.append((index, text))

    def setTabPresentation(
        self,
        index: int,
        *,
        primary_text: str,
        secondary_text: str,
        tooltip_text: str,
    ) -> None:
        """Record complete cube tab presentation updates."""

        self.tab_presentation_calls.append(
            (index, primary_text, secondary_text, tooltip_text)
        )
        self.setTabText(index, primary_text)

    def setTabIcon(self, index: int, icon) -> None:
        self.tab_icon_calls.append((index, icon))

    def tabItem(self, index: int) -> _FakeTabItem:
        return self.items[index]

    def setCurrentIndex(self, index: int) -> None:
        self.current_index_calls.append(index)

    def count(self) -> int:
        return len(self.items)


class _FakeEditorPanel:
    """Simple editor panel double for scroll calls and lifecycle simulation."""

    def __init__(self) -> None:
        self.scroll_calls: list[tuple[str, bool]] = []
        self.reveal_calls: list[str] = []
        self.alive = True

    def __bool__(self) -> bool:
        return self.alive

    def scroll_to_cube(self, alias: str, animated: bool = True) -> None:
        self.scroll_calls.append((alias, animated))

    def reveal_new_cube(self, route_key: str) -> None:
        self.reveal_calls.append(route_key)


class _FakeCubeIconFactory:
    """Record cube icon resolution requests and return a deterministic token."""

    def __init__(self) -> None:
        """Initialize empty icon resolution call history."""

        self.calls: list[tuple[str, str, object | None]] = []

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Record the requested cube and return a stable icon token."""

        _ = catalog_revision, cube_content_hash, render_size
        self.calls.append((cube_id, display_name, icon))
        return "resolved-icon-token"


class _FailingCubeIconFactory:
    """Record cube icon resolution requests and raise an expected failure."""

    def __init__(self) -> None:
        """Initialize empty icon resolution call history."""

        self.calls: list[tuple[str, str, object | None]] = []

    def icon_for_cube(
        self,
        *,
        cube_id: str,
        display_name: str,
        icon: object | None,
        catalog_revision: str = "",
        cube_content_hash: str = "",
        render_size: int | None = None,
    ) -> object:
        """Record the requested cube and raise a resolution failure."""

        _ = catalog_revision, cube_content_hash, render_size
        self.calls.append((cube_id, display_name, icon))
        raise RuntimeError("icon unavailable")


def _build_loader_state(module, alias_name: str):
    """Build focused callback state for cube-loader orchestration tests."""
    from substitute.domain.workflow import WorkflowState
    from substitute.application.node_behavior import NodeBehaviorRuntimeState

    materialized: list[tuple[str, str]] = []
    refresh_calls: list[tuple[str, str]] = []

    cube_stack_service = SimpleNamespace(loaded_cubes={}, added=[])

    def _apply_cube_addition(workflow, cube_id: str, alias: str, cube_state) -> None:
        cube_stack_service.added.append((workflow, cube_id, alias, cube_state))
        workflow.cubes[alias] = cube_state
        workflow.stack_order.append(alias)

    def _resolve_unique_alias(workflow, requested_alias: str) -> str:
        if requested_alias not in workflow.cubes:
            return requested_alias
        suffix = 2
        while f"{requested_alias} {suffix}" in workflow.cubes:
            suffix += 1
        return f"{requested_alias} {suffix}"

    cube_stack_service.resolve_unique_alias = _resolve_unique_alias
    cube_stack_service.apply_cube_addition = _apply_cube_addition
    cube_stack_service.apply_reordered_aliases = lambda workflow, new_order: setattr(
        workflow, "stack_order", list(new_order)
    )

    state = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wfA",
            workflows={"wfA": WorkflowState(), "wfB": WorkflowState()},
        ),
        cube_stacks={
            "wfA": _FakeCubeStack(f"loading:{alias_name}"),
            "wfB": _FakeCubeStack("loading:Other"),
        },
        editor_panels={"wfA": _FakeEditorPanel(), "wfB": _FakeEditorPanel()},
        cube_stack_service=cube_stack_service,
        cube_icon_factory=_FakeCubeIconFactory(),
        materialize_loaded_cube_input_canvas=lambda workflow_id, alias: (
            materialized.append((workflow_id, alias))
        ),
        refresh_workflow_after_cube_load=lambda workflow_id, alias: (
            refresh_calls.append((workflow_id, alias))
        ),
    )

    def build_callbacks(cube_load_service: object):
        return module.CubeLoadUiCallbacks(
            workflow_session_service=state.workflow_session_service,
            cube_stacks=state.cube_stacks,
            editor_panels=state.editor_panels,
            cube_load_service=cube_load_service,
            cube_stack_service=state.cube_stack_service,
            materialize_loaded_cube_input_canvas=(
                state.materialize_loaded_cube_input_canvas
            ),
            refresh_workflow_after_cube_load=state.refresh_workflow_after_cube_load,
            prepare_node_behavior_runtime=lambda _loaded_cube, _alias: (
                NodeBehaviorRuntimeState()
            ),
            cube_icon_factory=state.cube_icon_factory,
            cube_load_execution_route_factory=_route_factory(
                module,
                ImmediateTaskSubmitter(),
            ),
        )

    return state, build_callbacks, materialized, refresh_calls


def _stub_cube_service(
    *,
    graph: dict | None = None,
    error: Exception | None = None,
    icon: object | None = None,
    ui_payload: dict[str, object] | None = None,
):
    """Build a simple cube-load service stub for loader orchestration tests."""
    from substitute.domain.workflow import CubeState

    class _Service:
        def load_cube_definition(self, _cube_id: str):
            if error is not None:
                raise error
            return SimpleNamespace(
                cube_id=_cube_id,
                version="1.0.0",
                display_name=f"{_cube_id} Display",
                graph=graph or {"nodes": {}},
                ui_payload=ui_payload,
                icon=icon,
            )

        def load_cube_definition_version(self, _cube_id: str, version: str):
            if error is not None:
                raise error
            return SimpleNamespace(
                cube_id=_cube_id,
                version=version,
                display_name=f"{_cube_id} Display",
                graph=graph or {"nodes": {}},
                ui_payload=ui_payload,
                icon=icon,
            )

        def merge_cube_buffer_patch(
            self,
            *,
            cube_buffer: dict,
            buffer_patch: dict,
            cube_definition: dict,
        ) -> None:
            del cube_definition
            cube_buffer.update(buffer_patch)

        def build_loaded_cube_runtime(
            self,
            cube_id: str,
            alias_name: str,
            *,
            buffer_patch: dict | None,
            runtime_state: object | None,
            loaded_cube_definition: object | None = None,
        ) -> SimpleNamespace:
            loaded = loaded_cube_definition or self.load_cube_definition(cube_id)
            cube_definition = loaded.graph
            cube_buffer = dict(cube_definition)
            if buffer_patch is not None:
                self.merge_cube_buffer_patch(
                    cube_buffer=cube_buffer,
                    buffer_patch=buffer_patch,
                    cube_definition=cube_definition,
                )
            ui_payload = (
                dict(loaded.ui_payload) if loaded.ui_payload is not None else None
            )
            if loaded.icon is not None:
                if ui_payload is None:
                    ui_payload = {}
                ui_payload["cube_icon"] = loaded.icon
            if ui_payload is not None:
                ui_payload["node_behavior_runtime"] = runtime_state
            cube_state = CubeState(
                cube_id=cube_id,
                version=loaded.version,
                alias=alias_name,
                original_cube=cube_definition,
                buffer=cube_buffer,
                display_name=loaded.display_name,
            )
            if ui_payload is not None:
                cube_state.ui = ui_payload
            return SimpleNamespace(
                cube_id=cube_id,
                version=loaded.version,
                display_name=loaded.display_name,
                cube_definition=cube_definition,
                cube_buffer=cube_buffer,
                cube_state=cube_state,
                ui_payload=ui_payload,
                icon=loaded.icon,
            )

    return _Service()


def test_load_cube_async_marks_placeholder_failed_when_service_load_fails(
    monkeypatch,
) -> None:
    """Service load failures should mark placeholder as failed."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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
    monkeypatch,
) -> None:
    """Missing cube service wiring should fail closed and log the attribute failure."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)

    log_calls: list[tuple[str, dict[str, object]]] = []

    def _capture_log_error(_logger, message: str, **context: object) -> None:
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
    monkeypatch,
) -> None:
    """Rejected definition submission should fail the load and release its route."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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
    monkeypatch,
) -> None:
    """Rejected runtime-build submission should fail once and release its route."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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


def test_load_cube_async_returns_early_when_captured_ui_targets_are_gone(
    monkeypatch,
) -> None:
    """If captured target stack/panel disappear before callback, loader should no-op."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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
    monkeypatch,
) -> None:
    """Completion should update the current placeholder index, not the captured index."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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


def test_load_cube_async_applies_fallback_icon_when_resolution_fails(
    monkeypatch,
) -> None:
    """Loaded cube placeholder promotion should never finish without an icon."""

    from substitute.presentation.resources.app_icon import AppIcon

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    state.cube_icon_factory = _FailingCubeIconFactory()

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {}})),
            submitter,
        ),
        cube_id="Org/Base-Cubes/Base.cube",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    submitter.run_next()
    submitter.run_next()
    _FakeQTimer.run_all()

    assert state.cube_stacks["wfA"].tab_icon_calls == [(0, AppIcon.CUBE_20_FILLED)]
    assert state.cube_icon_factory.calls == [
        ("Org/Base-Cubes/Base.cube", "Org/Base-Cubes/Base.cube Display", None)
    ]
    assert state.cube_stacks["wfA"].tabItem(0).routeKey() == "Alias1"
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_defers_runtime_build_to_second_worker(monkeypatch) -> None:
    """Definition completion should queue valid identifier text to a second worker."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, _materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(graph={"nodes": {"n1": {}}})
    runtime_builds: list[str] = []
    original_build_loaded_cube_runtime = service.build_loaded_cube_runtime

    def _build_loaded_cube_runtime(*args, **kwargs):
        runtime_builds.append("runtime")
        return original_build_loaded_cube_runtime(*args, **kwargs)

    service.build_loaded_cube_runtime = _build_loaded_cube_runtime
    callbacks = build_callbacks(service)
    submitter = _QueuedSubmitter()
    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        cube_load_execution_route_factory=_route_factory(module, submitter),
    )

    module.load_cube_async(
        callbacks,
        cube_id=("Artificial-Sweetener/Base-Cubes/Anima/Promptmask Detailer.cube"),
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    assert len(submitter.items) == 1
    submitter.run_next()
    assert runtime_builds == []
    assert len(submitter.items) == 1
    submitter.run_next()
    _FakeQTimer.run_all()

    assert runtime_builds == ["runtime"]
    loaded_cube = state.workflow_session_service.workflows["wfA"].cubes["Alias1"]
    assert loaded_cube.cube_id == (
        "Artificial-Sweetener/Base-Cubes/Anima/Promptmask Detailer.cube"
    )


def test_load_cube_async_scopes_worker_cancellation_tokens(monkeypatch) -> None:
    """Cube-load workers should receive owner-scoped cancellation generations."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, _materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )

    definition_request, definition_token, _definition_handle = submitter.items[0]
    assert definition_token.generation > 0
    assert (
        definition_request.identity.cancellation_generation
        == definition_token.generation
    )

    submitter.run_next()
    runtime_request, runtime_token, _runtime_handle = submitter.items[0]
    assert runtime_token.generation > definition_token.generation
    assert runtime_request.identity.cancellation_generation == runtime_token.generation

    submitter.run_next()
    _FakeQTimer.run_all()

    assert not definition_token.is_cancelled
    assert not runtime_token.is_cancelled
    assert "Alias1" in state.workflow_session_service.workflows["wfA"].cubes


def test_load_cube_async_splits_ui_handoff_across_timer_turns(monkeypatch) -> None:
    """Loaded cube UI refresh should yield between owned GUI commit phases."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    submitter = _QueuedSubmitter()
    finished_aliases: list[str | None] = []

    module.load_cube_async(
        _with_submitter(
            module,
            build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
            submitter,
        ),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )

    submitter.run_next()
    submitter.run_next()

    assert len(_FakeQTimer.queue) == 1
    _FakeQTimer.run_next()
    assert refresh == []
    assert materialized == []
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert refresh == [("wfA", "Alias1")]
    assert materialized == []
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == []

    _FakeQTimer.run_next()
    assert finished_aliases == ["Alias1"]


def test_load_cube_async_ignores_completion_when_placeholder_was_removed(
    monkeypatch,
) -> None:
    """Completion should not mutate workflow state after the placeholder disappears."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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


def test_load_cube_async_applies_loaded_cube_metadata_tooltip(monkeypatch) -> None:
    """Async loaded cube tabs should receive the formatted metadata tooltip."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(
        graph={"nodes": {"n1": {}}},
        ui_payload={
            "canonical_cube": {
                "cube_id": "ArtificialSweetener/Base-Cubes/Upscale.cube",
                "version": "2.0.0",
                "description": "Upscales images with detail-preserving defaults.",
                "metadata": {
                    "default_alias": "Diffusion Upscale",
                    "supported_models": ["SDXL 1.0", "SD 1.5"],
                    "tags": ["upscale", "detailer"],
                },
                "implementation": {"nodes": {"Secret": {}}},
            },
            "source": {"repo_ref": "ArtificialSweetener/Base-Cubes"},
        },
    )

    module.load_cube_async(
        build_callbacks(service),
        cube_id="ArtificialSweetener/Base-Cubes/Upscale.cube",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    tooltip = state.cube_stacks["wfA"].tab_presentation_calls[0][3]
    assert "<b>Diffusion Upscale</b>, v2.0.0" in tooltip
    assert "Base-Cubes by ArtificialSweetener" in tooltip
    assert "<b>Supported models:</b> SDXL 1.0, SD 1.5" in tooltip
    assert "<b>Description:</b> Upscales images" in tooltip
    assert "<b>Tags:</b> upscale, detailer" in tooltip
    assert "Secret" not in tooltip
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_applies_buffer_patch_before_persisting_cube_state(
    monkeypatch,
) -> None:
    """Buffer patch merge should run and affect persisted cube buffer."""
    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    cube_def = {"nodes": {"Node1": {"class_type": "KSampler"}}}

    merge_calls: list[tuple[dict, dict, dict]] = []

    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service(graph=cube_def)

    def _merge_service(
        *, cube_buffer: dict, buffer_patch: dict, cube_definition: dict
    ) -> None:
        merge_calls.append((cube_buffer, buffer_patch, cube_definition))
        cube_buffer["patched"] = True

    service.merge_cube_buffer_patch = _merge_service  # type: ignore[method-assign]
    patch = {"nodes": {"Node1": {"inputs": {"seed": 7}}}}
    module.load_cube_async(
        build_callbacks(service),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=patch,
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    cube_state = workflow.cubes["Alias1"]
    assert merge_calls and merge_calls[0][1] == patch
    assert merge_calls[0][2] is cube_def
    assert cube_state.buffer["patched"] is True
    assert cube_state.display_name == "Base Display"
    assert state.cube_stack_service.added
    assert state.cube_stacks["wfA"].tab_text_calls == [(0, "Alias1")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (
            0,
            "Alias1",
            "v1.0.0",
            '<div style="max-width: 420px; width: 420px; white-space: normal; '
            'word-wrap: break-word; overflow-wrap: anywhere;">'
            "<b>Base Display</b>, v1.0.0</div>",
        )
    ]
    assert state.cube_stacks["wfA"].tab_icon_calls == [(0, "resolved-icon-token")]
    assert state.cube_stacks["wfA"].tabItem(0).routeKey() == "Alias1"
    assert workflow.stack_order == ["Alias1"]
    assert refresh == [("wfA", "Alias1")]
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_uses_version_loader_for_pinned_recipe_buffer(
    monkeypatch,
) -> None:
    """Pinned recipe buffers should load the requested cube version."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, refresh = _build_loader_state(
        module, "Alias1"
    )
    service = _stub_cube_service()
    version_load_calls: list[tuple[str, str]] = []
    original_version_loader = service.load_cube_definition_version

    def _load_version(cube_id: str, version: str) -> object:
        version_load_calls.append((cube_id, version))
        return original_version_loader(cube_id, version)

    service.load_cube_definition_version = _load_version  # type: ignore[method-assign]

    module.load_cube_async(
        build_callbacks(service),
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch={
            "cube_id": "Base",
            "version": "1.2.3",
            "update_policy": "pinned",
        },
    )
    _FakeQTimer.run_all()

    workflow = state.workflow_session_service.workflows["wfA"]
    cube_state = workflow.cubes["Alias1"]
    assert version_load_calls == [("Base", "1.2.3")]
    assert cube_state.version == "1.2.3"
    assert materialized == [("wfA", "Alias1")]


def test_load_cube_async_preserves_existing_cube_when_second_alias_is_suffixed(
    monkeypatch,
) -> None:
    """Async completion should keep both cube entries when alias resolution already suffixed the second load."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, _refresh = _build_loader_state(
        module, "Shared 2"
    )
    existing_cube_state = SimpleNamespace(alias="Shared")
    workflow = state.workflow_session_service.workflows["wfA"]
    workflow.cubes["Shared"] = existing_cube_state
    workflow.stack_order = ["Shared"]

    existing_tab = _FakeTabItem("Shared")
    placeholder_tab = state.cube_stacks["wfA"].items[0]
    state.cube_stacks["wfA"].items = [existing_tab, placeholder_tab]
    state.cube_stacks["wfA"].itemMap = {
        "Shared": existing_tab,
        "loading:Shared 2": placeholder_tab,
    }

    module.load_cube_async(
        build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}})),
        cube_id="cube_b",
        alias_name="Shared 2",
        placeholder_index=1,
        buffer_patch=None,
    )
    _FakeQTimer.run_all()

    assert set(workflow.cubes) == {"Shared", "Shared 2"}
    assert workflow.stack_order == ["Shared", "Shared 2"]
    assert state.cube_stacks["wfA"].tab_text_calls == [(1, "Shared 2")]
    assert state.cube_stacks["wfA"].tab_presentation_calls == [
        (
            1,
            "Shared 2",
            "v1.0.0",
            '<div style="max-width: 420px; width: 420px; white-space: normal; '
            'word-wrap: break-word; overflow-wrap: anywhere;">'
            "<b>cube_b Display</b>, v1.0.0</div>",
        )
    ]
    assert state.cube_stacks["wfA"].tabItem(1).routeKey() == "Shared 2"
    assert materialized == [("wfA", "Shared 2")]


def test_load_cube_async_can_refresh_without_revealing_for_batch_load(
    monkeypatch,
) -> None:
    """Batch loads should refresh inserted cubes and defer activation/reveal."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    refresh_only_calls: list[tuple[str, str]] = []
    finished_aliases: list[str | None] = []
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_loaded_cube_surface=lambda workflow_id, alias, **_kwargs: (
            refresh_only_calls.append((workflow_id, alias)) or True
        ),
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_all()

    assert refresh_calls == []
    assert refresh_only_calls == [("wfA", "Alias1")]
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]
    assert state.editor_panels["wfA"].reveal_calls == []


def test_load_cube_async_excludes_loading_placeholders_from_workflow_order(
    monkeypatch,
) -> None:
    """Workflow stack order sync should ignore staged placeholders not loaded yet."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, _refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    stack = state.cube_stacks["wfA"]
    stack.items.append(_FakeTabItem("loading:Alias2"))
    stack.items.append(_FakeTabItem("Already Loaded"))
    stack.itemMap["loading:Alias2"] = stack.items[1]
    stack.itemMap["Already Loaded"] = stack.items[2]
    workflow = state.workflow_session_service.workflows["wfA"]
    workflow.cubes["Already Loaded"] = object()
    workflow.stack_order.append("Already Loaded")
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    finished_aliases: list[str | None] = []

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_all()

    assert workflow.stack_order == ["Alias1", "Already Loaded"]
    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]


def test_load_cube_async_waits_for_async_editor_refresh_before_finishing(
    monkeypatch,
) -> None:
    """Cube-load completion should wait for progressive editor build completion."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    refresh_completions: list[Callable[[], None]] = []
    finished_aliases: list[str | None] = []

    def refresh_async(workflow_id: str, alias: str, done: Callable[[], None]) -> None:
        """Record the async refresh request and hold completion for assertions."""

        refresh_calls.append((workflow_id, alias))
        refresh_completions.append(done)

    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_workflow_after_cube_load_async=refresh_async,
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_next()
    _FakeQTimer.run_next()

    assert refresh_calls == [("wfA", "Alias1")]
    assert refresh_completions
    assert materialized == []
    assert finished_aliases == []

    refresh_completions.pop()()
    _FakeQTimer.run_all()

    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]


def test_load_cube_async_finishes_after_silent_async_refresh(
    monkeypatch,
) -> None:
    """Silent staged loads should continue after async editor insertion completes."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
    state, build_callbacks, materialized, refresh_calls = _build_loader_state(
        module, "Alias1"
    )
    callbacks = build_callbacks(_stub_cube_service(graph={"nodes": {"n1": {}}}))
    refresh_completions: list[Callable[[bool], None]] = []
    refresh_kwargs: list[dict[str, object]] = []
    finished_aliases: list[str | None] = []

    def refresh_async(
        workflow_id: str,
        alias: str,
        done: Callable[[bool], None],
        **kwargs: object,
    ) -> None:
        """Record the silent async refresh request and hold completion."""

        refresh_calls.append((workflow_id, alias))
        refresh_kwargs.append(kwargs)
        refresh_completions.append(done)

    callbacks = module.CubeLoadUiCallbacks(
        workflow_session_service=callbacks.workflow_session_service,
        cube_stacks=callbacks.cube_stacks,
        editor_panels=callbacks.editor_panels,
        cube_load_service=callbacks.cube_load_service,
        cube_stack_service=callbacks.cube_stack_service,
        materialize_loaded_cube_input_canvas=(
            callbacks.materialize_loaded_cube_input_canvas
        ),
        refresh_workflow_after_cube_load=callbacks.refresh_workflow_after_cube_load,
        prepare_node_behavior_runtime=callbacks.prepare_node_behavior_runtime,
        cube_icon_factory=callbacks.cube_icon_factory,
        refresh_loaded_cube_surface_async=refresh_async,
        cube_load_execution_route_factory=callbacks.cube_load_execution_route_factory,
    )

    module.load_cube_async(
        callbacks,
        cube_id="Base",
        alias_name="Alias1",
        placeholder_index=0,
        buffer_patch=None,
        reveal_after_load=False,
        on_load_finished=lambda alias: finished_aliases.append(alias),
    )
    _FakeQTimer.run_next()
    _FakeQTimer.run_next()

    assert refresh_calls == [("wfA", "Alias1")]
    assert refresh_kwargs == [{"wait_for_complete": True}]
    assert materialized == []

    refresh_completions.pop()(True)
    _FakeQTimer.run_all()

    assert materialized == [("wfA", "Alias1")]
    assert finished_aliases == ["Alias1"]


def test_load_cube_async_marks_placeholder_failed_for_invalid_cube_contract(
    monkeypatch,
) -> None:
    """Cube-load service errors should mark placeholder failed without state mutation."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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
    monkeypatch,
) -> None:
    """Cube loader should fail closed when the load service rejects a cube id."""

    module = _import_cube_loader_module(monkeypatch)
    _FakeQTimer.clear()
    monkeypatch.setattr(module, "QTimer", _FakeQTimer)
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
