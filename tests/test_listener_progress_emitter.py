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

"""Tests for Comfy listener progress emission."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.application.ports.comfy_gateway import ProgressUpdate
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    WebsocketProgressEmission,
)
from substitute.infrastructure.comfy.listener_progress_emitter import (
    ListenerProgressContext,
    ListenerProgressEmitter,
    emit_listener_progress,
)

_EMITTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_progress_emitter.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TraceRecorder:
    """Record progress trace calls for assertions."""

    def __init__(self) -> None:
        """Initialize an empty trace call list."""

        self.calls: list[dict[str, object]] = []

    def trace_estimator_progress(
        self,
        *,
        source_event: str,
        prompt_id: str,
        workflow_percent: float | None,
        sampler_percent: float | None,
    ) -> None:
        """Record one progress estimator trace call."""

        self.calls.append(
            {
                "source_event": source_event,
                "prompt_id": prompt_id,
                "workflow_percent": workflow_percent,
                "sampler_percent": sampler_percent,
            }
        )


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_listener_progress_emitter_imports_no_ui_or_listener_boundaries() -> None:
    """Progress emission must stay independent of UI and listener code."""

    source = _EMITTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_emit_listener_progress_traces_and_dispatches_progress_update() -> None:
    """Progress emission should preserve listener callback and trace payloads."""

    trace = _TraceRecorder()
    progress_events: list[ProgressUpdate] = []

    emit_listener_progress(
        context=ListenerProgressContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
        ),
        trace=trace,
        source_event="progress_state",
        workflow_percent=37.5,
        sampler_percent=50.0,
        on_progress=progress_events.append,
    )

    assert trace.calls == [
        {
            "source_event": "progress_state",
            "prompt_id": "pid-1",
            "workflow_percent": 37.5,
            "sampler_percent": 50.0,
        }
    ]
    assert progress_events == [
        ProgressUpdate(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=37.5,
            sampler_percent=50.0,
        )
    ]


def test_listener_progress_emitter_dispatches_routed_progress_update() -> None:
    """Progress emitter should adapt routed progress updates to callbacks."""

    trace = _TraceRecorder()
    progress_events: list[ProgressUpdate] = []
    emitter = ListenerProgressEmitter(
        context=ListenerProgressContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
        ),
        trace=trace,
        on_progress=progress_events.append,
    )

    emitter.emit(
        WebsocketProgressEmission(
            source_event="progress_state",
            workflow_percent=37.5,
            sampler_percent=50.0,
        )
    )

    assert trace.calls == [
        {
            "source_event": "progress_state",
            "prompt_id": "pid-1",
            "workflow_percent": 37.5,
            "sampler_percent": 50.0,
        }
    ]
    assert progress_events == [
        ProgressUpdate(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=37.5,
            sampler_percent=50.0,
        )
    ]
