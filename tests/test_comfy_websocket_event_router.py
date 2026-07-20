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

"""Tests for stateful Comfy JSON websocket event routing."""

from __future__ import annotations

import ast
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.errors import RuntimeReportContext
from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
)
from substitute.application.ports.comfy_gateway import ModelLoadProgressUpdate
from substitute.infrastructure.comfy.comfy_execution_timing import (
    ComfyExecutionTimingTracker,
)
from substitute.infrastructure.comfy.comfy_websocket_event_router import (
    ComfyWebsocketEventRouter,
    WebsocketJsonRouteResult,
)


@dataclass(frozen=True)
class _SourceIdentity:
    """Provide timing attribution fields for routed executing events."""

    source_key: str = "wf-1:1"
    cube_alias: str = "CubeA"


@dataclass
class _Clock:
    """Return deterministic millisecond timestamps for timing tests."""

    values: list[float]
    last_value: float = 0.0

    def __call__(self) -> float:
        """Return the next configured timestamp, then repeat the last one."""

        if self.values:
            self.last_value = self.values.pop(0)
        return self.last_value


@dataclass
class _CubeOutputHandler:
    """Record cube-output payloads routed through the JSON router."""

    payloads: list[Mapping[str, object]] = field(default_factory=list)

    def handle(self, data: Mapping[str, object]) -> None:
        """Record one cube-output payload."""

        self.payloads.append(data)


def _prompt_nodes() -> dict[str, dict[str, object]]:
    """Return a minimal single-node prompt used by routing tests."""

    return {"1": {"class_type": "KSampler"}}


def _router(
    *,
    cube_output_handler: _CubeOutputHandler | None = None,
    model_load_updates: list[ModelLoadProgressUpdate] | None = None,
) -> ComfyWebsocketEventRouter:
    """Build a JSON event router with deterministic collaborators."""

    prompt_nodes = _prompt_nodes()
    return ComfyWebsocketEventRouter(
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        all_node_ids=set(prompt_nodes),
        prompt_nodes=prompt_nodes,
        timing_tracker=ComfyExecutionTimingTracker(
            workflow_id="wf-1",
            prompt_id="pid-1",
            clock_ms=_Clock([1000.0, 1200.0, 1500.0]),
        ),
        progress_tracker=ComfyWorkflowProgressTracker.from_prompt(prompt_nodes),
        source_identity_resolver=lambda _node_id: _SourceIdentity(),
        source_metadata_resolver=lambda _source_node_id, _all_node_ids: (
            "source-key",
            "CubeA",
        ),
        cube_output_handler=cube_output_handler or _CubeOutputHandler(),
        runtime_context_provider=lambda: RuntimeReportContext(
            comfy_version="0.3.1",
            pytorch_version="2.8.0",
        ),
        on_model_load_progress=(
            model_load_updates.append if model_load_updates is not None else _ignore
        ),
    )


def _ignore(_event: ModelLoadProgressUpdate) -> None:
    """Ignore model-load progress events outside dedicated assertions."""


def test_comfy_websocket_event_router_keeps_infrastructure_boundary() -> None:
    """JSON routing must stay Qt-free and listener-independent."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "comfy_websocket_event_router.py"
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


def test_route_executed_event_returns_progress_emission() -> None:
    """Executed events should update progress and request listener progress emit."""

    result = _router().route_message(
        message_type="executed",
        data={"prompt_id": "pid-1", "node": "1"},
    )

    assert result.progress_emission is not None
    assert result.progress_emission.source_event == "executed"
    assert result.progress_emission.workflow_percent == 100.0
    assert result.progress_emission.sampler_percent is None
    assert result.prompt_finished is False


def test_route_executing_done_returns_terminal_progress() -> None:
    """Executing prompt completion should request 100 percent terminal progress."""

    router = _router()
    router.route_message(
        message_type="executing",
        data={"prompt_id": "pid-1", "node": "1"},
    )

    result = router.route_message(
        message_type="executing",
        data={"prompt_id": "pid-1", "node": None},
    )

    assert result.progress_emission is not None
    assert result.progress_emission.source_event == "executing_done"
    assert result.progress_emission.workflow_percent == 100.0
    assert result.progress_emission.sampler_percent is None
    assert result.prompt_finished is True


def test_route_execution_error_returns_failure_report() -> None:
    """Active execution_error events should return listener failure details."""

    result = _router().route_message(
        message_type="execution_error",
        data={
            "prompt_id": "pid-1",
            "node_id": "1",
            "node_type": "KSampler",
            "exception_type": "RuntimeError",
            "exception_message": "sampler failed",
            "timestamp": 1500.0,
        },
    )

    assert result.failure is not None
    assert result.failure.message == "RuntimeError: sampler failed"
    assert result.failure.detail is not None
    assert result.failure.error_report is not None
    assert render_source_application_text(result.failure.error_report.title) == (
        "KSampler failed"
    )
    assert result.failure.error_report.runtime.comfy_version == "0.3.1"


def test_route_cube_output_delegates_payload() -> None:
    """Substitute cube-output messages should be delegated to the handler port."""

    cube_output_handler = _CubeOutputHandler()
    payload: dict[str, object] = {"prompt_id": "pid-1", "node_id": "out-1"}

    result = _router(cube_output_handler=cube_output_handler).route_message(
        message_type="substitute_cube_output",
        data=payload,
    )

    assert result == WebsocketJsonRouteResult()
    assert cube_output_handler.payloads == [payload]


def test_unknown_progress_node_logs_prompt_safe_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown progress nodes should be ignored with workflow/prompt context."""

    with caplog.at_level(
        logging.WARNING,
        logger="sugarsubstitute.infrastructure.comfy.comfy_websocket_event_router",
    ):
        result = _router().route_message(
            message_type="progress",
            data={"prompt_id": "pid-1", "node": "missing", "value": 1, "max": 2},
        )

    assert result == WebsocketJsonRouteResult()
    assert any(
        "Ignoring progress for unknown Comfy node" in record.message
        and "workflow_id=wf-1" in record.message
        and "prompt_id=pid-1" in record.message
        and "node_id=missing" in record.message
        for record in caplog.records
    )
