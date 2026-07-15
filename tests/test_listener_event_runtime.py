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

"""Tests for Comfy listener event-runtime collaborator assembly."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

from substitute.application.ports.comfy_gateway import (
    ListenerCallbacks,
    ListenerSessionHandle,
    ListenerStartRequest,
    ProgressUpdate,
)
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    WebsocketProgressEmission,
)
from substitute.infrastructure.comfy.listener_event_runtime import (
    build_listener_event_runtime,
)
from substitute.infrastructure.comfy.listener_progress_emitter import (
    ListenerProgressContext,
)
from substitute.infrastructure.comfy.output_source_identity_resolver import (
    OutputSourceIdentity,
)
from substitute.domain.onboarding import ComfyEndpoint

_RUNTIME_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "listener_event_runtime.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TraceRecorder:
    """Record runtime trace callback payloads."""

    def __init__(self) -> None:
        """Initialize empty trace call collections."""

        self.messages: list[dict[str, object]] = []
        self.progress: list[dict[str, object]] = []

    def trace_message(
        self,
        *,
        message: dict[str, object],
        active_prompt_id: str,
        prompt_nodes: dict[str, object],
    ) -> None:
        """Record one traced text message."""

        self.messages.append(
            {
                "message": message,
                "active_prompt_id": active_prompt_id,
                "prompt_nodes": prompt_nodes,
            }
        )

    def trace_estimator_progress(
        self,
        *,
        source_event: str,
        prompt_id: str,
        workflow_percent: float | None,
        sampler_percent: float | None,
    ) -> None:
        """Record one traced progress estimate."""

        self.progress.append(
            {
                "source_event": source_event,
                "prompt_id": prompt_id,
                "workflow_percent": workflow_percent,
                "sampler_percent": sampler_percent,
            }
        )


class _CubeOutputHandler:
    """Provide the cube-output handler protocol for runtime construction."""

    def handle(self, data: Mapping[str, object]) -> None:
        """Accept routed cube-output payloads."""

        return None


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_listener_event_runtime_imports_no_ui_or_listener_boundaries() -> None:
    """Event runtime assembly must stay independent of UI and listener code."""

    source = _RUNTIME_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in _FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_listener_event_runtime_builds_engine_callbacks_and_progress_sink() -> None:
    """Runtime assembly should preserve trace and progress callback behavior."""

    trace = _TraceRecorder()
    progress_events: list[ProgressUpdate] = []
    runtime = build_listener_event_runtime(
        request=_request(),
        callbacks=_callbacks(progress_events),
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        progress_context=ListenerProgressContext(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
        ),
        source_identity_resolver=lambda node_id: OutputSourceIdentity(
            node_id=node_id,
            source_key=f"source-{node_id}",
            source_label=f"Source {node_id}",
            cube_alias="Cube",
        ),
        source_metadata_resolver=lambda _source_node_id, _all_node_ids: (
            None,
            None,
        ),
        cube_output_handler=_CubeOutputHandler(),
        trace_factory=lambda: trace,
        clock_ms=lambda: 1000.0,
    )

    runtime.engine_callbacks.on_text_message(
        {"type": "execution_start", "data": {"prompt_id": "pid-1"}}
    )
    runtime.engine_callbacks.on_progress(
        WebsocketProgressEmission(
            source_event="progress_state",
            workflow_percent=25.0,
            sampler_percent=50.0,
        )
    )

    assert runtime.all_node_ids == {"1"}
    assert trace.messages == [
        {
            "message": {"type": "execution_start", "data": {"prompt_id": "pid-1"}},
            "active_prompt_id": "pid-1",
            "prompt_nodes": {"1": {"class_type": "KSampler"}},
        }
    ]
    assert trace.progress == [
        {
            "source_event": "progress_state",
            "prompt_id": "pid-1",
            "workflow_percent": 25.0,
            "sampler_percent": 50.0,
        }
    ]
    assert progress_events == [
        ProgressUpdate(
            workflow_id="wf-1",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            workflow_percent=25.0,
            sampler_percent=50.0,
        )
    ]


def _request() -> ListenerStartRequest:
    """Build a listener request with one valid and one malformed prompt node."""

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
        workflow_payload={
            "1": {"class_type": "KSampler"},
            "malformed": object(),
        },
        sugar_script="line one",
        workflow_id="wf-1",
        workflow_name="Workflow",
    )


def _callbacks(progress_events: list[ProgressUpdate]) -> ListenerCallbacks:
    """Build callbacks required by event-runtime construction."""

    return ListenerCallbacks(
        on_progress=progress_events.append,
        on_model_load_progress=lambda _event: None,
        on_preview=lambda _event: None,
        on_output_image=lambda _event: None,
        on_failed=lambda _event: None,
        on_timing=lambda _event: None,
        on_completed=lambda _event: None,
    )
