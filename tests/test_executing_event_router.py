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

"""Tests for Comfy executing event routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.executing_event_router import (
    route_executing_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "executing_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TimingRecorder:
    """Record timing calls emitted by executing routing."""

    def __init__(self) -> None:
        """Initialize empty timing call lists."""

        self.finished_nodes: list[str] = []
        self.running_nodes: list[tuple[str, str]] = []

    def mark_finished(self, node_id: str) -> None:
        """Record a finished timing node."""

        self.finished_nodes.append(node_id)

    def mark_running(self, *, node_id: str, source_identity: str) -> None:
        """Record a running timing node and its source identity."""

        self.running_nodes.append((node_id, source_identity))


class _ProgressRecorder:
    """Record progress calls emitted by executing routing."""

    def __init__(self) -> None:
        """Initialize empty progress call lists."""

        self.finished_nodes: list[str] = []
        self.running_nodes: list[str] = []
        self.prompt_finished = False

    def mark_finished(self, node_id: str) -> None:
        """Record a finished progress node."""

        self.finished_nodes.append(node_id)

    def mark_running(self, node_id: str) -> None:
        """Record a running progress node."""

        self.running_nodes.append(node_id)

    def finish_prompt(self) -> None:
        """Record prompt completion."""

        self.prompt_finished = True


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _source_identity(node_id: str) -> str:
    """Return a deterministic test source identity for a node."""

    return f"source:{node_id}"


def test_executing_router_imports_no_ui_or_listener_boundaries() -> None:
    """Executing routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_executing_event_marks_node_running() -> None:
    """executing should mark the normalized active node as running."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "pid-1", "node": "internal", "display_node": 2},
        active_prompt_id="pid-1",
        all_node_ids={"2"},
        current_node=None,
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.current_node == "2"
    assert result.emit_progress_source == "executing"
    assert result.prompt_finished is False
    assert timing_tracker.running_nodes == [("2", "source:2")]
    assert progress_tracker.running_nodes == ["2"]


def test_route_executing_event_finishes_previous_node_without_progress_state() -> None:
    """Next-node executing events should finish the previous node when needed."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "pid-1", "node": "2"},
        active_prompt_id="pid-1",
        all_node_ids={"1", "2"},
        current_node="1",
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.current_node == "2"
    assert timing_tracker.finished_nodes == ["1"]
    assert progress_tracker.finished_nodes == ["1"]
    assert timing_tracker.running_nodes == [("2", "source:2")]


def test_route_executing_event_preserves_progress_state_completion_ownership() -> None:
    """Progress-state-aware runs should not finish previous nodes on next-node events."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "pid-1", "node": "2"},
        active_prompt_id="pid-1",
        all_node_ids={"1", "2"},
        current_node="1",
        progress_state_seen=True,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.current_node == "2"
    assert timing_tracker.finished_nodes == []
    assert progress_tracker.finished_nodes == []
    assert timing_tracker.running_nodes == [("2", "source:2")]


def test_route_executing_event_finishes_prompt() -> None:
    """A null executing node should finish the current node and prompt."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "pid-1", "node": None},
        active_prompt_id="pid-1",
        all_node_ids={"1"},
        current_node="1",
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.current_node is None
    assert result.emit_progress_source == "executing_done"
    assert result.prompt_finished is True
    assert timing_tracker.finished_nodes == ["1"]
    assert progress_tracker.finished_nodes == ["1"]
    assert progress_tracker.prompt_finished is True


def test_route_executing_event_reports_unknown_nodes_without_mutation() -> None:
    """Unknown executing nodes should be consumed and reported to the listener."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "pid-1", "node": "missing"},
        active_prompt_id="pid-1",
        all_node_ids={"1"},
        current_node="1",
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.current_node == "1"
    assert result.unknown_node_id == "missing"
    assert result.emit_progress_source is None
    assert timing_tracker.finished_nodes == []
    assert progress_tracker.running_nodes == []


def test_route_executing_event_ignores_other_prompts() -> None:
    """executing events for other prompts should be consumed without mutation."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "executing",
        {"prompt_id": "other", "node": "1"},
        active_prompt_id="pid-1",
        all_node_ids={"1"},
        current_node="1",
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.current_node == "1"
    assert timing_tracker.running_nodes == []
    assert progress_tracker.running_nodes == []


def test_route_executing_event_ignores_unknown_event_types() -> None:
    """Non-executing events should be left for later routing."""

    timing_tracker = _TimingRecorder()
    progress_tracker = _ProgressRecorder()

    result = route_executing_event(
        "progress",
        {"prompt_id": "pid-1", "node": "1"},
        active_prompt_id="pid-1",
        all_node_ids={"1"},
        current_node="1",
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is False
    assert result.current_node == "1"
    assert timing_tracker.running_nodes == []
    assert progress_tracker.running_nodes == []
