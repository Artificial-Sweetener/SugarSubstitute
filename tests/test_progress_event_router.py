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

"""Tests for Comfy progress event routing."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.infrastructure.comfy.progress_event_router import (
    route_progress_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "progress_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _ProgressRecorder:
    """Record progress calls emitted by progress routing."""

    def __init__(self) -> None:
        """Initialize empty progress call lists."""

        self.running_nodes: list[str] = []
        self.sampler_progress: list[tuple[str, float | None]] = []

    def mark_running(self, node_id: str) -> None:
        """Record a running progress node."""

        self.running_nodes.append(node_id)

    def mark_sampler_progress(self, node_id: str, fraction: float | None) -> None:
        """Record sampler progress for one node."""

        self.sampler_progress.append((node_id, fraction))


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return imported module names from a parsed Python syntax tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_progress_router_imports_no_ui_or_listener_boundaries() -> None:
    """Progress routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_progress_event_marks_sampler_progress() -> None:
    """Sampler progress should record sampler fraction and request emission."""

    progress_tracker = _ProgressRecorder()

    result = route_progress_event(
        "progress",
        {"prompt_id": "pid-1", "node": "2", "value": 3, "max": 10},
        active_prompt_id="pid-1",
        all_node_ids={"2"},
        prompt_nodes={"2": {"class_type": "KSampler"}},
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is True
    assert result.sampler_percent == 30.0
    assert result.unknown_node_id is None
    assert progress_tracker.sampler_progress == [("2", 0.3)]
    assert progress_tracker.running_nodes == []


def test_route_progress_event_marks_running_when_sampler_percent_missing() -> None:
    """Malformed sampler progress should preserve the listener's running fallback."""

    progress_tracker = _ProgressRecorder()

    result = route_progress_event(
        "progress",
        {"prompt_id": "pid-1", "node": "2", "value": 3, "max": 0},
        active_prompt_id="pid-1",
        all_node_ids={"2"},
        prompt_nodes={"2": {"class_type": "KSampler"}},
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is True
    assert result.sampler_percent is None
    assert progress_tracker.sampler_progress == []
    assert progress_tracker.running_nodes == ["2"]


def test_route_progress_event_marks_non_sampler_running() -> None:
    """Non-sampler progress should mark the node running and emit workflow progress."""

    progress_tracker = _ProgressRecorder()

    result = route_progress_event(
        "progress",
        {"prompt_id": "pid-1", "node": "3.child", "value": 1, "max": 2},
        active_prompt_id="pid-1",
        all_node_ids={"3"},
        prompt_nodes={"3": {"class_type": "VAEDecode"}},
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is True
    assert result.sampler_percent is None
    assert progress_tracker.running_nodes == ["3"]


def test_route_progress_event_reports_unknown_nodes_without_mutation() -> None:
    """Unknown progress nodes should be consumed and reported to the listener."""

    progress_tracker = _ProgressRecorder()

    result = route_progress_event(
        "progress",
        {"prompt_id": "pid-1", "node": "missing"},
        active_prompt_id="pid-1",
        all_node_ids={"3"},
        prompt_nodes={"3": {"class_type": "VAEDecode"}},
        progress_tracker=progress_tracker,
    )

    assert result.handled is True
    assert result.emit_progress is False
    assert result.unknown_node_id == "missing"
    assert progress_tracker.running_nodes == []
    assert progress_tracker.sampler_progress == []


def test_route_progress_event_ignores_malformed_or_other_prompt_events() -> None:
    """Malformed and other-prompt progress events should be consumed without mutation."""

    progress_tracker = _ProgressRecorder()

    other_prompt = route_progress_event(
        "progress",
        {"prompt_id": "other", "node": "3"},
        active_prompt_id="pid-1",
        all_node_ids={"3"},
        prompt_nodes={"3": {"class_type": "VAEDecode"}},
        progress_tracker=progress_tracker,
    )
    malformed = route_progress_event(
        "progress",
        {"prompt_id": "pid-1", "node": None},
        active_prompt_id="pid-1",
        all_node_ids={"3"},
        prompt_nodes={"3": {"class_type": "VAEDecode"}},
        progress_tracker=progress_tracker,
    )

    assert other_prompt.handled is True
    assert malformed.handled is True
    assert progress_tracker.running_nodes == []
    assert progress_tracker.sampler_progress == []


def test_route_progress_event_ignores_unknown_event_types() -> None:
    """Non-progress events should be left for later routing."""

    progress_tracker = _ProgressRecorder()

    result = route_progress_event(
        "executing",
        {"prompt_id": "pid-1", "node": "3"},
        active_prompt_id="pid-1",
        all_node_ids={"3"},
        prompt_nodes={"3": {"class_type": "VAEDecode"}},
        progress_tracker=progress_tracker,
    )

    assert result.handled is False
    assert result.emit_progress is False
    assert progress_tracker.running_nodes == []
