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

"""Tests for Comfy listener terminal callback dispatch."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from substitute.application.errors import ErrorReport, ErrorReportKind
from substitute.application.ports.comfy_gateway import (
    GenerationExecutionTiming,
    ListenerCallbacks,
    ListenerCompleted,
    ListenerFailure,
    ListenerSessionHandle,
    ListenerStartRequest,
    ModelLoadProgressUpdate,
    OutputImageUpdate,
    PreviewImageUpdate,
    ProgressUpdate,
)
from substitute.infrastructure.comfy.listener_callback_dispatcher import (
    ListenerCallbackDispatcher,
)
from substitute.infrastructure.comfy.websocket_listener_engine import (
    ListenerEngineInterrupted,
)


@dataclass
class _CallbackSink:
    """Collect listener callback events for dispatcher assertions."""

    failures: list[ListenerFailure] = field(default_factory=list)
    completed: list[ListenerCompleted] = field(default_factory=list)

    def callbacks(self) -> ListenerCallbacks:
        """Return callbacks backed by this sink."""

        return ListenerCallbacks(
            on_progress=self._ignore_progress,
            on_model_load_progress=self._ignore_model_load_progress,
            on_preview=self._ignore_preview,
            on_output_image=self._ignore_output_image,
            on_failed=self.failures.append,
            on_timing=self._ignore_timing,
            on_completed=self.completed.append,
        )

    @staticmethod
    def _ignore_progress(_event: ProgressUpdate) -> None:
        """Ignore progress events outside terminal-dispatch tests."""

    @staticmethod
    def _ignore_model_load_progress(_event: ModelLoadProgressUpdate) -> None:
        """Ignore model-load events outside terminal-dispatch tests."""

    @staticmethod
    def _ignore_preview(_event: PreviewImageUpdate) -> None:
        """Ignore preview events outside terminal-dispatch tests."""

    @staticmethod
    def _ignore_output_image(_event: OutputImageUpdate) -> None:
        """Ignore output events outside terminal-dispatch tests."""

    @staticmethod
    def _ignore_timing(_event: GenerationExecutionTiming) -> None:
        """Ignore timing events outside terminal-dispatch tests."""


@dataclass
class _TimingEmitter:
    """Record failure-timing emission and optionally raise."""

    calls: list[bool] = field(default_factory=list)
    fail: bool = False

    def emit_once(self, *, count_active_nodes: bool) -> None:
        """Record emission arguments and raise when configured."""

        self.calls.append(count_active_nodes)
        if self.fail:
            raise RuntimeError("timing failed")


class _ReportedError(RuntimeError):
    """Carry listener failure details as execution errors do."""

    def __init__(self, report: ErrorReport) -> None:
        """Initialize with stable detail and report payloads."""

        super().__init__("generation failed")
        self.detail = "node failed detail"
        self.error_report = report


def _request() -> ListenerStartRequest:
    """Return a listener request with stable identifying fields."""

    return ListenerStartRequest(
        prompt_id="prompt-1",
        generation_run_id="run-1",
        client_id="client-1",
        listener_session=ListenerSessionHandle(
            workflow_id="workflow-1",
            generation_run_id="run-1",
            client_id="client-1",
            session=object(),
        ),
        output_dir=Path("outputs"),
        workflow_payload={},
        sugar_script="",
        workflow_id="workflow-1",
        workflow_name="Workflow",
    )


def _dispatcher(
    sink: _CallbackSink,
    *,
    disconnect: bool = False,
) -> ListenerCallbackDispatcher:
    """Build a dispatcher with deterministic callbacks and disconnect policy."""

    return ListenerCallbackDispatcher(
        request=_request(),
        callbacks=sink.callbacks(),
        is_disconnect_error=lambda _error: disconnect,
    )


def test_listener_callback_dispatcher_keeps_infrastructure_boundary() -> None:
    """Terminal callback dispatch must stay Qt-free and listener-independent."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "listener_callback_dispatcher.py"
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


def test_emit_failure_delivers_typed_failure_and_failure_timing() -> None:
    """Failure dispatch should emit failure timing and preserve report detail."""

    sink = _CallbackSink()
    timing_emitter = _TimingEmitter()
    report = ErrorReport(
        kind=ErrorReportKind.EXECUTION,
        title="KSampler failed",
        message="generation failed",
        stage="listen",
    )

    _dispatcher(sink).emit_failure(
        _ReportedError(report),
        timing_emitter=timing_emitter,
    )

    assert timing_emitter.calls == [False]
    assert sink.failures == [
        ListenerFailure(
            workflow_id="workflow-1",
            generation_run_id="run-1",
            prompt_id="prompt-1",
            error="generation failed",
            detail="node failed detail",
            error_report=report,
        )
    ]


def test_emit_failure_logs_timing_failure_and_still_delivers_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Timing callback failure should not suppress listener failure delivery."""

    sink = _CallbackSink()
    timing_emitter = _TimingEmitter(fail=True)

    with caplog.at_level(
        logging.ERROR,
        logger="sugarsubstitute.infrastructure.comfy.listener_callback_dispatcher",
    ):
        _dispatcher(sink).emit_failure(
            RuntimeError("listener failed"),
            timing_emitter=timing_emitter,
        )

    assert timing_emitter.calls == [False]
    assert sink.failures[0].error == "listener failed"
    assert any(
        "Failed to emit generation execution timing" in record.message
        and "workflow_id=workflow-1" in record.message
        and "prompt_id=prompt-1" in record.message
        for record in caplog.records
    )


def test_emit_failure_logs_disconnect_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Disconnect failures should log as warnings with run context."""

    sink = _CallbackSink()

    with caplog.at_level(
        logging.WARNING,
        logger="sugarsubstitute.infrastructure.comfy.listener_callback_dispatcher",
    ):
        _dispatcher(sink, disconnect=True).emit_failure(
            ConnectionError("closed"),
            timing_emitter=None,
        )

    assert sink.failures[0].error == "closed"
    assert any(
        "Comfy websocket listener disconnected before prompt completion"
        in record.message
        and "generation_run_id=run-1" in record.message
        and "reason=websocket_disconnected" in record.message
        for record in caplog.records
    )


def test_interruption_logs_terminal_info_without_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Expected prompt interruption should not emit exception diagnostics."""

    sink = _CallbackSink()
    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.listener_callback_dispatcher",
    ):
        _dispatcher(sink).emit_failure(
            ListenerEngineInterrupted("Generation interrupted"),
            timing_emitter=None,
        )

    record = next(
        record
        for record in caplog.records
        if "Comfy generation interrupted" in record.message
    )
    assert record.levelno == logging.INFO
    assert record.exc_info is None
    assert sink.failures[0].error == "Generation interrupted"


def test_emit_completed_delivers_typed_completion() -> None:
    """Completion dispatch should emit the terminal completion DTO."""

    sink = _CallbackSink()

    _dispatcher(sink).emit_completed()

    assert sink.completed == [
        ListenerCompleted(
            workflow_id="workflow-1",
            generation_run_id="run-1",
            prompt_id="prompt-1",
        )
    ]
