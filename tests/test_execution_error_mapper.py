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

"""Tests for Comfy execution_error mapping."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from sugarsubstitute_shared.localization import render_source_application_text

from substitute.application.errors import RuntimeReportContext
from substitute.infrastructure.comfy.execution_error_mapper import (
    format_execution_error,
    route_execution_error_event,
)

_MAPPER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "execution_error_mapper.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TimingRecorder:
    """Record prompt terminal timing emitted by execution_error mapping."""

    def __init__(self) -> None:
        """Initialize an empty timing call list."""

        self.terminal_timestamps: list[float | None] = []

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record one terminal timestamp."""

        self.terminal_timestamps.append(timestamp_ms)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_execution_error_mapper_imports_no_ui_or_listener_boundaries() -> None:
    """Execution-error mapping must stay independent of UI and listener code."""

    source = _MAPPER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_format_execution_error_combines_type_message_and_traceback_lines() -> None:
    """Execution errors should preserve the current compact message and traceback."""

    message, detail = format_execution_error(
        {
            "exception_type": "ModuleNotFoundError",
            "exception_message": "No module named 'xformers'",
            "traceback": ["Traceback line 1", "", "Traceback line 2"],
        }
    )

    assert message == "ModuleNotFoundError: No module named 'xformers'"
    assert detail == "Traceback line 1\nTraceback line 2"


def test_format_execution_error_uses_message_or_type_fallbacks() -> None:
    """Missing type or message fields should preserve listener fallback behavior."""

    assert format_execution_error({"exception_message": "bad"})[0] == "bad"
    assert format_execution_error({"exception_type": "BadNode"})[0] == "BadNode"
    assert format_execution_error({})[0] == "Comfy execution failed"


def test_format_execution_error_uses_string_traceback() -> None:
    """String traceback values should be surfaced directly as detail."""

    message, detail = format_execution_error(
        {
            "exception_type": "RuntimeError",
            "traceback": "single traceback",
        }
    )

    assert message == "RuntimeError"
    assert detail == "single traceback"


def test_format_execution_error_falls_back_to_sorted_payload_json() -> None:
    """Errors without traceback should serialize the payload as diagnostic detail."""

    _message, detail = format_execution_error({"b": 2, "a": 1})

    assert detail == json.dumps({"b": 2, "a": 1}, default=str, sort_keys=True)


def test_route_execution_error_event_builds_failure_payload() -> None:
    """Active execution_error events should build message, detail, report, and timing."""

    timing_tracker = _TimingRecorder()

    result = route_execution_error_event(
        "execution_error",
        {
            "prompt_id": "pid-1",
            "timestamp": 1200,
            "exception_type": "ModuleNotFoundError",
            "exception_message": "No module named 'xformers'",
            "node_id": "12",
            "node_type": "KSampler",
            "traceback": ["Traceback line 1", "Traceback line 2"],
            "current_inputs": {"seed": 123},
        },
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
        runtime_context_provider=lambda: RuntimeReportContext(
            comfy_version="0.3.1",
            pytorch_version="2.8.0",
        ),
    )

    assert result.handled is True
    assert result.error_message == "ModuleNotFoundError: No module named 'xformers'"
    assert result.error_detail == "Traceback line 1\nTraceback line 2"
    assert result.error_report is not None
    assert render_source_application_text(result.error_report.title) == (
        "KSampler failed"
    )
    assert result.error_report.workflow_id == "wf-1"
    assert result.error_report.runtime.comfy_version == "0.3.1"
    assert result.error_report.runtime.pytorch_version == "2.8.0"
    assert result.error_report.node is not None
    assert result.error_report.node.node_id == "12"
    assert result.error_report.node.current_inputs == {"seed": 123}
    assert timing_tracker.terminal_timestamps == [1200.0]


def test_route_execution_error_event_consumes_other_prompt_without_runtime_lookup() -> (
    None
):
    """Execution errors for other prompts should not build reports or timing."""

    timing_tracker = _TimingRecorder()
    runtime_requested = False

    def runtime_context() -> RuntimeReportContext:
        nonlocal runtime_requested
        runtime_requested = True
        return RuntimeReportContext()

    result = route_execution_error_event(
        "execution_error",
        {"prompt_id": "other", "exception_type": "RuntimeError"},
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
        runtime_context_provider=runtime_context,
    )

    assert result.handled is True
    assert result.error_message is None
    assert result.error_report is None
    assert timing_tracker.terminal_timestamps == []
    assert runtime_requested is False


def test_route_execution_error_event_ignores_unknown_event_types() -> None:
    """Non-execution_error events should be left for later routing."""

    timing_tracker = _TimingRecorder()

    result = route_execution_error_event(
        "progress",
        {"prompt_id": "pid-1"},
        workflow_id="wf-1",
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
        runtime_context_provider=RuntimeReportContext,
    )

    assert result.handled is False
    assert result.error_message is None
    assert timing_tracker.terminal_timestamps == []
