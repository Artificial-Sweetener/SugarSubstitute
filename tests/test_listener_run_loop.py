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

"""Tests for composed listener run-loop execution."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
)
from substitute.domain.onboarding import ComfyEndpoint
from substitute.infrastructure.comfy.listener_run_loop import run_listener_runtime
from substitute.infrastructure.comfy.listener_runtime_composition import (
    ListenerRuntimeComposition,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ListenerEngineResult,
)

_RUN_LOOP_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_run_loop.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _Session:
    """Record websocket session close calls."""

    def __init__(self) -> None:
        """Initialize fake websocket state."""

        self.websocket_client = object()
        self.closed = False

    def close(self) -> None:
        """Record that the session was closed."""

        self.closed = True


class _ConnectionManager:
    """Return one prebuilt session from the listener connection port."""

    def __init__(self, session: _Session) -> None:
        """Store the session returned by open."""

        self.session = session
        self.opened = False

    def open(self) -> _Session:
        """Return the fake websocket session."""

        self.opened = True
        return self.session


class _TimingEmitter:
    """Record terminal timing emission calls."""

    def __init__(self) -> None:
        """Initialize timing emission state."""

        self.count_active_nodes_values: list[bool] = []

    def emit_once(self, *, count_active_nodes: bool) -> None:
        """Record one emit request."""

        self.count_active_nodes_values.append(count_active_nodes)


class _CallbackDispatcher:
    """Record listener terminal callback dispatches."""

    def __init__(self) -> None:
        """Initialize callback records."""

        self.failures: list[tuple[Exception, object | None]] = []
        self.completed_count = 0

    def emit_failure(
        self,
        error: Exception,
        *,
        timing_emitter: object | None,
    ) -> None:
        """Record a failure dispatch."""

        self.failures.append((error, timing_emitter))

    def emit_completed(self) -> None:
        """Record a completion dispatch."""

        self.completed_count += 1


class _Engine:
    """Record engine construction and return a configured result."""

    result = ListenerEngineResult(prompt_finished=True)
    error: Exception | None = None
    constructed_kwargs: list[dict[str, object]] = []

    def __init__(self, **kwargs: object) -> None:
        """Record engine construction kwargs."""

        self.constructed_kwargs.append(kwargs)

    def run(self) -> ListenerEngineResult:
        """Return or raise the configured engine outcome."""

        if self.error is not None:
            raise self.error
        return self.result


def test_listener_run_loop_imports_no_ui_or_listener_boundaries() -> None:
    """Run-loop execution must stay independent of UI and listener facade code."""

    source = _RUN_LOOP_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_listener_run_loop_emits_success_timing_and_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Successful prompt completion should emit final timing and completion."""

    session = _Session()
    connection_manager = _ConnectionManager(session)
    dispatcher = _CallbackDispatcher()
    timing_emitter = _TimingEmitter()
    event_runtime = _event_runtime(timing_emitter)
    _Engine.result = ListenerEngineResult(prompt_finished=True)
    _Engine.error = None
    _Engine.constructed_kwargs = []
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.listener_run_loop.build_listener_event_runtime",
        lambda **_kwargs: event_runtime,
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.listener_run_loop.ComfyWebsocketListenerEngine",
        _Engine,
    )

    run_listener_runtime(
        request=_request(),
        callbacks=_callbacks(),
        runtime=_runtime(
            connection_manager=connection_manager,
            dispatcher=dispatcher,
        ),
    )

    assert connection_manager.opened is True
    assert session.closed is True
    assert timing_emitter.count_active_nodes_values == [True]
    assert dispatcher.failures == []
    assert dispatcher.completed_count == 1
    assert _Engine.constructed_kwargs == [
        {
            "websocket_client": session.websocket_client,
            "receive_timeout_seconds": 5.0,
            "active_prompt_id": "pid-1",
            "prompt_liveness_probe": _Engine.constructed_kwargs[0][
                "prompt_liveness_probe"
            ],
            "all_node_ids": {"1"},
            "json_event_router": event_runtime.json_event_router,
            "binary_event_router": "binary-router",
            "callbacks": event_runtime.engine_callbacks,
        }
    ]


def test_listener_run_loop_dispatches_failure_and_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Engine failures should dispatch failure, close, and completion."""

    session = _Session()
    dispatcher = _CallbackDispatcher()
    timing_emitter = _TimingEmitter()
    failure = RuntimeError("boom")
    _Engine.result = ListenerEngineResult(prompt_finished=True)
    _Engine.error = failure
    _Engine.constructed_kwargs = []
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.listener_run_loop.build_listener_event_runtime",
        lambda **_kwargs: _event_runtime(timing_emitter),
    )
    monkeypatch.setattr(
        "substitute.infrastructure.comfy.listener_run_loop.ComfyWebsocketListenerEngine",
        _Engine,
    )

    run_listener_runtime(
        request=_request(),
        callbacks=_callbacks(),
        runtime=_runtime(
            connection_manager=_ConnectionManager(session),
            dispatcher=dispatcher,
        ),
    )

    assert session.closed is True
    assert timing_emitter.count_active_nodes_values == []
    assert dispatcher.failures == [(failure, timing_emitter)]
    assert dispatcher.completed_count == 1


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _event_runtime(timing_emitter: _TimingEmitter) -> SimpleNamespace:
    """Build a fake event runtime."""

    return SimpleNamespace(
        timing_emitter=timing_emitter,
        all_node_ids={"1"},
        json_event_router="json-router",
        engine_callbacks="engine-callbacks",
    )


def _runtime(
    *,
    connection_manager: _ConnectionManager,
    dispatcher: _CallbackDispatcher,
) -> ListenerRuntimeComposition:
    """Build a structurally compatible runtime composition fake."""

    return cast(
        ListenerRuntimeComposition,
        SimpleNamespace(
            endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
            receive_timeout_seconds=5.0,
            prompt_liveness_probe=object(),
            websocket_connection_manager=connection_manager,
            callback_dispatcher=dispatcher,
            progress_context=object(),
            output_source_resolver=SimpleNamespace(
                resolve=lambda _node_id: object(),
            ),
            cube_output_handler=object(),
            model_load_source_metadata_resolver=SimpleNamespace(
                resolve=lambda _source_node_id, _all_node_ids: (None, None),
            ),
            binary_event_router="binary-router",
            cube_output_node_ids=set(),
        ),
    )


def _request() -> ListenerStartRequest:
    """Build a listener start request for run-loop tests."""

    return ListenerStartRequest(
        prompt_id="pid-1",
        generation_run_id="run-1",
        client_id="client-1",
        listener_session=ListenerSessionHandle(
            workflow_id="wf-1",
            generation_run_id="run-1",
            client_id="client-1",
            session=object(),
        ),
        output_dir=Path("out"),
        workflow_payload={"1": {"class_type": "KSampler"}},
        sugar_script="line one",
        workflow_id="wf-1",
        workflow_name="Workflow",
    )


def _callbacks() -> ListenerCallbacks:
    """Build callbacks required by run-loop execution."""

    return ListenerCallbacks(
        on_progress=lambda _event: None,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )
