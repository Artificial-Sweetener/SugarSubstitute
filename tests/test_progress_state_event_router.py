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

"""Tests for Comfy progress_state event routing."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.application.generation.progress_estimation import (
    ComfyWorkflowProgressTracker,
)
from substitute.infrastructure.comfy.progress_state_event_router import (
    route_progress_state_event,
)

_ROUTER_MODULE = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "infrastructure"
    / "comfy"
    / "progress_state_event_router.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure.comfy.websocket_listener",
)


class _TimingRecorder:
    """Record timing calls emitted by progress_state routing."""

    def __init__(self) -> None:
        """Initialize empty timing call lists."""

        self.running_nodes: list[tuple[str, str]] = []
        self.finished_nodes: list[str] = []
        self.failed_nodes: list[str] = []

    def mark_running(self, *, node_id: str, source_identity: str) -> None:
        """Record a running timing node and its source identity."""

        self.running_nodes.append((node_id, source_identity))

    def mark_finished(self, node_id: str) -> None:
        """Record a finished timing node."""

        self.finished_nodes.append(node_id)

    def mark_failed(self, node_id: str) -> None:
        """Record a failed timing node."""

        self.failed_nodes.append(node_id)


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


def test_progress_state_router_imports_no_ui_or_listener_boundaries() -> None:
    """Progress-state routing must stay independent of UI and listener code."""

    source = _ROUTER_MODULE.read_text(encoding="utf-8")
    imported_modules = _imported_module_names(ast.parse(source))

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        if imported_module.startswith(_FORBIDDEN_IMPORT_PREFIXES)
    }

    assert forbidden_imports == set()


def test_route_progress_state_event_updates_timing_progress_and_sampler() -> None:
    """Progress-state entries should update timing, tracker state, and sampler percent."""

    timing_tracker = _TimingRecorder()
    progress_tracker = ComfyWorkflowProgressTracker.from_prompt(
        {
            "text": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
            "failed": {"class_type": "VAEDecode"},
        }
    )

    result = route_progress_state_event(
        "progress_state",
        {
            "prompt_id": "pid-1",
            "nodes": {
                "text": {"state": "finished", "value": 1, "max": 1},
                "sampler": {"state": "running", "value": 5, "max": 10},
                "failed": {"state": "error", "value": 0, "max": 1},
            },
        },
        active_prompt_id="pid-1",
        all_node_ids={"text", "sampler", "failed"},
        prompt_nodes={
            "text": {"class_type": "CLIPTextEncode"},
            "sampler": {"class_type": "KSampler"},
            "failed": {"class_type": "VAEDecode"},
        },
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.progress_state_seen is True
    assert result.emit_progress is True
    assert result.sampler_percent == 50.0
    assert timing_tracker.finished_nodes == ["text"]
    assert timing_tracker.running_nodes == [("sampler", "source:sampler")]
    assert timing_tracker.failed_nodes == ["failed"]
    assert progress_tracker.workflow_percent() == pytest.approx(50.0)


def test_route_progress_state_event_normalizes_child_nodes() -> None:
    """Dynamic child ids should route through their owning workflow node."""

    timing_tracker = _TimingRecorder()
    progress_tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"owner": {"class_type": "KSampler"}}
    )

    result = route_progress_state_event(
        "progress_state",
        {
            "prompt_id": "pid-1",
            "nodes": {
                "owner.0.1": {
                    "display_node_id": "owner",
                    "state": "running",
                    "value": 2,
                    "max": 4,
                }
            },
        },
        active_prompt_id="pid-1",
        all_node_ids={"owner"},
        prompt_nodes={"owner": {"class_type": "KSampler"}},
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.progress_state_seen is True
    assert result.sampler_percent == 50.0
    assert timing_tracker.running_nodes == [("owner", "source:owner")]
    assert progress_tracker.workflow_percent() == pytest.approx(50.0)


def test_route_progress_state_event_consumes_empty_or_other_prompt_events() -> None:
    """Empty and other-prompt progress_state events should not mutate state."""

    timing_tracker = _TimingRecorder()
    progress_tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"sampler": {"class_type": "KSampler"}}
    )

    other_prompt = route_progress_state_event(
        "progress_state",
        {
            "prompt_id": "other",
            "nodes": {"sampler": {"state": "finished", "value": 1, "max": 1}},
        },
        active_prompt_id="pid-1",
        all_node_ids={"sampler"},
        prompt_nodes={"sampler": {"class_type": "KSampler"}},
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )
    malformed = route_progress_state_event(
        "progress_state",
        {"prompt_id": "pid-1", "nodes": {"sampler": "bad"}},
        active_prompt_id="pid-1",
        all_node_ids={"sampler"},
        prompt_nodes={"sampler": {"class_type": "KSampler"}},
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert other_prompt.handled is True
    assert other_prompt.progress_state_seen is False
    assert malformed.handled is True
    assert malformed.progress_state_seen is False
    assert timing_tracker.finished_nodes == []
    assert progress_tracker.workflow_percent() == 0.0


def test_route_progress_state_event_marks_seen_for_unknown_owner_entries() -> None:
    """Parsed entries without known owners should still count as seen progress_state."""

    timing_tracker = _TimingRecorder()
    progress_tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"sampler": {"class_type": "KSampler"}}
    )

    result = route_progress_state_event(
        "progress_state",
        {
            "prompt_id": "pid-1",
            "nodes": {"unknown": {"state": "finished", "value": 1, "max": 1}},
        },
        active_prompt_id="pid-1",
        all_node_ids={"sampler"},
        prompt_nodes={"sampler": {"class_type": "KSampler"}},
        progress_state_seen=False,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is True
    assert result.progress_state_seen is True
    assert result.emit_progress is True
    assert result.sampler_percent is None
    assert timing_tracker.finished_nodes == []
    assert progress_tracker.workflow_percent() == 0.0


def test_route_progress_state_event_ignores_unknown_event_types() -> None:
    """Non-progress_state events should be left for later routing."""

    timing_tracker = _TimingRecorder()
    progress_tracker = ComfyWorkflowProgressTracker.from_prompt(
        {"sampler": {"class_type": "KSampler"}}
    )

    result = route_progress_state_event(
        "progress",
        {"prompt_id": "pid-1"},
        active_prompt_id="pid-1",
        all_node_ids={"sampler"},
        prompt_nodes={"sampler": {"class_type": "KSampler"}},
        progress_state_seen=True,
        timing_tracker=timing_tracker,
        progress_tracker=progress_tracker,
        source_identity_resolver=_source_identity,
    )

    assert result.handled is False
    assert result.progress_state_seen is True
    assert result.emit_progress is False
