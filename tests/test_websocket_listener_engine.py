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

"""Tests for the Qt-free Comfy websocket listener receive engine."""

from __future__ import annotations

import ast
import json
import socket
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    WebsocketExecutionFailure,
    WebsocketJsonRouteResult,
    WebsocketProgressEmission,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ComfyWebsocketListenerEngine,
    ListenerEngineCallbacks,
    ListenerEngineExecutionError,
    ListenerEngineInterrupted,
)
from substitute.infrastructure.comfy.prompt_liveness import (
    PromptLivenessObservation,
    PromptLivenessState,
)


@dataclass
class _Client:
    """Return configured websocket payloads and record timeout updates."""

    payloads: list[object]
    timeout_seconds: float | None = None

    def connect(self, *_args: object, **_kwargs: object) -> object:
        """Satisfy the websocket-client protocol."""

        return None

    def send(self, _payload: str) -> object:
        """Satisfy the websocket-client protocol."""

        return None

    def recv(self) -> object:
        """Return the next payload or fail when none remains."""

        if not self.payloads:
            raise AssertionError("unexpected recv")
        payload = self.payloads.pop(0)
        if isinstance(payload, BaseException):
            raise payload
        return payload

    def close(self) -> object:
        """Satisfy the websocket-client protocol."""

        return None

    def settimeout(self, timeout_seconds: float) -> None:
        """Record receive-timeout application."""

        self.timeout_seconds = timeout_seconds


@dataclass
class _JsonRouter:
    """Return configured route results and record parsed messages."""

    results: list[WebsocketJsonRouteResult]
    calls: list[tuple[object, Mapping[str, object]]] = field(default_factory=list)

    def route_message(
        self,
        *,
        message_type: object,
        data: Mapping[str, object],
    ) -> WebsocketJsonRouteResult:
        """Record parsed routing input and return the next result."""

        self.calls.append((message_type, data))
        return self.results.pop(0)


@dataclass
class _BinaryRouter:
    """Record raw binary route requests."""

    calls: list[tuple[object, set[str]]] = field(default_factory=list)

    def route_event(self, event_payload: object, *, all_node_ids: set[str]) -> None:
        """Record one binary route invocation."""

        self.calls.append((event_payload, set(all_node_ids)))


@dataclass
class _LivenessProbe:
    """Return configured prompt observations and record prompt identifiers."""

    observations: list[PromptLivenessObservation]
    calls: list[str] = field(default_factory=list)

    def observe(self, prompt_id: str) -> PromptLivenessObservation:
        """Return the next configured liveness observation."""

        self.calls.append(prompt_id)
        return self.observations.pop(0)


def _active_probe() -> _LivenessProbe:
    """Build an unused active-prompt probe for non-timeout tests."""

    return _LivenessProbe(
        [PromptLivenessObservation(state="active", detail="still active")]
    )


def _text_payload(message_type: str, data: Mapping[str, object]) -> str:
    """Build a Comfy websocket text payload."""

    return json.dumps({"type": message_type, "data": dict(data)})


def test_websocket_listener_engine_keeps_infrastructure_boundary() -> None:
    """The listener engine must not import Qt, presentation, or the runnable."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "websocket_listener_engine.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "PySide6",
        "qfluentwidgets",
        "qframelesswindow",
        "substitute.presentation",
        "substitute.infrastructure.comfy.websocket_listener",
    }

    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    assert not {
        module
        for module in imported_modules
        for forbidden in forbidden_roots
        if module == forbidden or module.startswith(f"{forbidden}.")
    }


def test_engine_routes_text_progress_and_returns_on_prompt_finished() -> None:
    """Text payloads should be parsed, traced, routed, and emitted in order."""

    client = _Client(
        [
            _text_payload("progress", {"prompt_id": "pid-1"}),
            _text_payload("executing", {"prompt_id": "pid-1", "node": None}),
        ]
    )
    json_router = _JsonRouter(
        [
            WebsocketJsonRouteResult(
                progress_emission=WebsocketProgressEmission(
                    source_event="progress",
                    workflow_percent=50.0,
                    sampler_percent=25.0,
                )
            ),
            WebsocketJsonRouteResult(prompt_finished=True),
        ]
    )
    traced_messages: list[Mapping[str, object]] = []
    progress_events: list[WebsocketProgressEmission] = []

    result = ComfyWebsocketListenerEngine(
        websocket_client=client,
        receive_timeout_seconds=12.5,
        active_prompt_id="pid-1",
        prompt_liveness_probe=_active_probe(),
        all_node_ids={"1"},
        json_event_router=json_router,
        binary_event_router=_BinaryRouter(),
        callbacks=ListenerEngineCallbacks(
            on_text_message=traced_messages.append,
            on_progress=progress_events.append,
        ),
    ).run()

    assert client.timeout_seconds == 12.5
    assert result.prompt_finished is True
    assert [call[0] for call in json_router.calls] == ["progress", "executing"]
    assert progress_events == [
        WebsocketProgressEmission(
            source_event="progress",
            workflow_percent=50.0,
            sampler_percent=25.0,
        )
    ]
    assert traced_messages == [
        {"type": "progress", "data": {"prompt_id": "pid-1"}},
        {"type": "executing", "data": {"prompt_id": "pid-1", "node": None}},
    ]


def test_engine_routes_binary_payloads_before_terminal_text() -> None:
    """Binary payloads should go directly to the binary router."""

    binary_router = _BinaryRouter()

    result = ComfyWebsocketListenerEngine(
        websocket_client=_Client([b"preview-bytes", _text_payload("done", {})]),
        receive_timeout_seconds=5.0,
        active_prompt_id="pid-1",
        prompt_liveness_probe=_active_probe(),
        all_node_ids={"1", "2"},
        json_event_router=_JsonRouter([WebsocketJsonRouteResult(prompt_finished=True)]),
        binary_event_router=binary_router,
        callbacks=ListenerEngineCallbacks(
            on_text_message=lambda _message: None,
            on_progress=lambda _progress: None,
        ),
    ).run()

    assert result.prompt_finished is True
    assert binary_router.calls == [(b"preview-bytes", {"1", "2"})]


def test_engine_continues_after_timeout_while_prompt_remains_active() -> None:
    """A silent active prompt should continue until Comfy reports completion."""

    probe = _LivenessProbe(
        [
            PromptLivenessObservation(state="active", detail="still active"),
            PromptLivenessObservation(state="active", detail="still active"),
        ]
    )
    result = ComfyWebsocketListenerEngine(
        websocket_client=_Client(
            [
                socket.timeout("timed out"),
                socket.timeout("still timed out"),
                _text_payload("executing", {"prompt_id": "pid-1", "node": None}),
            ]
        ),
        receive_timeout_seconds=3.0,
        active_prompt_id="pid-1",
        prompt_liveness_probe=probe,
        all_node_ids=set(),
        json_event_router=_JsonRouter([WebsocketJsonRouteResult(prompt_finished=True)]),
        binary_event_router=_BinaryRouter(),
        callbacks=ListenerEngineCallbacks(
            on_text_message=lambda _message: None,
            on_progress=lambda _progress: None,
        ),
    ).run()

    assert result.prompt_finished is True
    assert probe.calls == ["pid-1", "pid-1"]


def test_engine_accepts_history_success_after_receive_timeout() -> None:
    """A missed terminal websocket event should defer to successful history."""

    result = ComfyWebsocketListenerEngine(
        websocket_client=_Client([socket.timeout("timed out")]),
        receive_timeout_seconds=3.0,
        active_prompt_id="pid-1",
        prompt_liveness_probe=_LivenessProbe(
            [PromptLivenessObservation(state="succeeded", detail="completed")]
        ),
        all_node_ids=set(),
        json_event_router=_JsonRouter([]),
        binary_event_router=_BinaryRouter(),
        callbacks=ListenerEngineCallbacks(
            on_text_message=lambda _message: None,
            on_progress=lambda _progress: None,
        ),
    ).run()

    assert result.prompt_finished is True


@pytest.mark.parametrize(
    ("state", "error_type", "message"),
    [
        ("failed", ListenerEngineExecutionError, "reported prompt failure"),
        ("missing", TimeoutError, "could not be found"),
        ("unavailable", ConnectionError, "Unable to verify"),
    ],
)
def test_engine_fails_only_after_verified_non_active_timeout_state(
    state: PromptLivenessState,
    error_type: type[Exception],
    message: str,
) -> None:
    """Terminal, missing, and unreachable prompts should fail distinctly."""

    with pytest.raises(error_type, match=message):
        ComfyWebsocketListenerEngine(
            websocket_client=_Client([socket.timeout("timed out")]),
            receive_timeout_seconds=3.0,
            active_prompt_id="pid-1",
            prompt_liveness_probe=_LivenessProbe(
                [PromptLivenessObservation(state=state, detail="probe detail")]
            ),
            all_node_ids=set(),
            json_event_router=_JsonRouter([]),
            binary_event_router=_BinaryRouter(),
            callbacks=ListenerEngineCallbacks(
                on_text_message=lambda _message: None,
                on_progress=lambda _progress: None,
            ),
        ).run()


def test_engine_normalizes_disconnect() -> None:
    """Disconnect transport errors should use listener failure wording."""

    with pytest.raises(ConnectionError, match="connection closed before generation"):
        ComfyWebsocketListenerEngine(
            websocket_client=_Client([ConnectionError("closed")]),
            receive_timeout_seconds=3.0,
            active_prompt_id="pid-1",
            prompt_liveness_probe=_active_probe(),
            all_node_ids=set(),
            json_event_router=_JsonRouter([]),
            binary_event_router=_BinaryRouter(),
            callbacks=ListenerEngineCallbacks(
                on_text_message=lambda _message: None,
                on_progress=lambda _progress: None,
            ),
        ).run()


def test_engine_raises_routed_execution_failure_with_report() -> None:
    """Execution failures from JSON routing should preserve detail and report."""

    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="sampler failed",
        stage="listen",
    )

    with pytest.raises(ListenerEngineExecutionError) as caught:
        ComfyWebsocketListenerEngine(
            websocket_client=_Client([_text_payload("execution_error", {})]),
            receive_timeout_seconds=3.0,
            active_prompt_id="pid-1",
            prompt_liveness_probe=_active_probe(),
            all_node_ids=set(),
            json_event_router=_JsonRouter(
                [
                    WebsocketJsonRouteResult(
                        failure=WebsocketExecutionFailure(
                            message="RuntimeError: sampler failed",
                            detail="traceback",
                            error_report=report,
                        )
                    )
                ]
            ),
            binary_event_router=_BinaryRouter(),
            callbacks=ListenerEngineCallbacks(
                on_text_message=lambda _message: None,
                on_progress=lambda _progress: None,
            ),
        ).run()

    assert str(caught.value) == "RuntimeError: sampler failed"
    assert caught.value.detail == "traceback"
    assert caught.value.error_report is report


def test_engine_raises_typed_interruption_for_interrupted_route() -> None:
    """Interrupted prompts should remain distinguishable from execution faults."""

    with pytest.raises(ListenerEngineInterrupted, match="Generation interrupted"):
        ComfyWebsocketListenerEngine(
            websocket_client=_Client([_text_payload("execution_interrupted", {})]),
            receive_timeout_seconds=3.0,
            active_prompt_id="pid-1",
            prompt_liveness_probe=_active_probe(),
            all_node_ids=set(),
            json_event_router=_JsonRouter([WebsocketJsonRouteResult(interrupted=True)]),
            binary_event_router=_BinaryRouter(),
            callbacks=ListenerEngineCallbacks(
                on_text_message=lambda _message: None,
                on_progress=lambda _progress: None,
            ),
        ).run()
