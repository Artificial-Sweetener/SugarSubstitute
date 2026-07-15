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

"""Tests for Comfy prompt lifecycle event routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.prompt_lifecycle_event_router import (
    route_prompt_lifecycle_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "prompt_lifecycle_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TimingRecorder:
    """Record prompt timing calls emitted by lifecycle routing."""

    def __init__(self) -> None:
        """Initialize an empty call list."""

        self.calls: list[tuple[str, float | None]] = []

    def mark_prompt_started(self, timestamp_ms: float | None) -> None:
        """Record a prompt start call."""

        self.calls.append(("started", timestamp_ms))

    def mark_prompt_terminal(self, timestamp_ms: float | None) -> None:
        """Record a prompt terminal call."""

        self.calls.append(("terminal", timestamp_ms))


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_prompt_lifecycle_router_imports_no_ui_or_listener_boundaries() -> None:
    """Prompt lifecycle routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_prompt_lifecycle_event_marks_prompt_start() -> None:
    """execution_start should mark the active prompt as started."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_start",
        {"prompt_id": "pid-1", "timestamp": 125.5},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == [("started", 125.5)]


def test_route_prompt_lifecycle_event_marks_prompt_success() -> None:
    """execution_success should mark the active prompt as terminal."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_success",
        {"prompt_id": "pid-1", "timestamp": 300},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == [("terminal", 300.0)]


def test_route_prompt_lifecycle_event_reports_interruption() -> None:
    """execution_interrupted should mark terminal timing and request failure."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_interrupted",
        {"prompt_id": "pid-1", "timestamp": "missing"},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is True
    assert timing_tracker.calls == [("terminal", None)]


def test_route_prompt_lifecycle_event_ignores_other_prompt_ids() -> None:
    """Lifecycle events for other prompts should be consumed without timing."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "execution_success",
        {"prompt_id": "other", "timestamp": 100},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is True
    assert result.interrupted is False
    assert timing_tracker.calls == []


def test_route_prompt_lifecycle_event_ignores_unknown_event_types() -> None:
    """Non-lifecycle events should be left for later routing."""

    timing_tracker = _TimingRecorder()

    result = route_prompt_lifecycle_event(
        "progress",
        {"prompt_id": "pid-1", "timestamp": 100},
        active_prompt_id="pid-1",
        timing_tracker=timing_tracker,
    )

    assert result.handled is False
    assert result.interrupted is False
    assert timing_tracker.calls == []
