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

"""Tests for Comfy cached and executed node event routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.node_execution_event_router import (
    route_node_execution_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "node_execution_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TimingRecorder:
    """Record timing calls emitted by node execution routing."""

    def __init__(self) -> None:
        """Initialize empty call lists."""

        self.cached_nodes: list[str] = []
        self.finished_nodes: list[str] = []

    def mark_cached(self, node_id: str) -> None:
        """Record a cached timing node."""

        self.cached_nodes.append(node_id)

    def mark_finished(self, node_id: str) -> None:
        """Record a finished timing node."""

        self.finished_nodes.append(node_id)


class _ProgressRecorder:
    """Record progress calls emitted by node execution routing."""

    def __init__(self) -> None:
        """Initialize empty call lists."""

        self.cached_nodes: list[str] = []
        self.finished_nodes: list[str] = []

    def mark_cached(self, node_id: str) -> None:
        """Record a cached progress node."""

        self.cached_nodes.append(node_id)

    def mark_finished(self, node_id: str) -> None:
        """Record a finished progress node."""

        self.finished_nodes.append(node_id)


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_node_execution_router_imports_no_ui_or_listener_boundaries() -> None:
    """Node execution routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_node_execution_event_marks_cached_known_nodes() -> None:
    """execution_cached should mark normalized cached nodes on both trackers."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_node_execution_event(
        "execution_cached",
        {"prompt_id": "pid-1", "nodes": ["2", "3.subnode", "unknown"]},
        active_prompt_id="pid-1",
        all_node_ids={"1", "2", "3"},
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is False
    assert timing_tracker.cached_nodes == ["2", "3"]
    assert progress_tracker.cached_nodes == ["2", "3"]


def test_route_node_execution_event_ignores_cached_nodes_for_other_prompts() -> None:
    """execution_cached for another prompt should be consumed without mutation."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_node_execution_event(
        "execution_cached",
        {"prompt_id": "other", "nodes": ["2"]},
        active_prompt_id="pid-1",
        all_node_ids={"2"},
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is False
    assert timing_tracker.cached_nodes == []
    assert progress_tracker.cached_nodes == []


def test_route_node_execution_event_marks_executed_node_and_requests_progress() -> None:
    """executed should mark one normalized node and request progress emission."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_node_execution_event(
        "executed",
        {"prompt_id": "pid-1", "node": "internal", "display_node": 4},
        active_prompt_id="pid-1",
        all_node_ids={"4"},
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is True
    assert timing_tracker.finished_nodes == ["4"]
    assert progress_tracker.finished_nodes == ["4"]


def test_route_node_execution_event_ignores_unknown_executed_nodes() -> None:
    """executed should be consumed without progress when no workflow node matches."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_node_execution_event(
        "executed",
        {"prompt_id": "pid-1", "node": "unknown"},
        active_prompt_id="pid-1",
        all_node_ids={"4"},
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is False
    assert timing_tracker.finished_nodes == []
    assert progress_tracker.finished_nodes == []


def test_route_node_execution_event_ignores_unknown_event_types() -> None:
    """Non-node-execution events should be left for later routing."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_node_execution_event(
        "progress",
        {"prompt_id": "pid-1", "node": "4"},
        active_prompt_id="pid-1",
        all_node_ids={"4"},
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
    )

    assert result.handled is False
    assert result.emit_progress is False
    assert timing_tracker.cached_nodes == []
    assert progress_tracker.cached_nodes == []
