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

"""Tests for Comfy execution timing ownership."""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from substitute.application.ports.comfy_gateway import GenerationExecutionTiming
from substitute.infrastructure.comfy.comfy_execution_timing import (
    ComfyExecutionTimingEmitter,
    ComfyExecutionTimingTracker,
)


@dataclass(frozen=True)
class _SourceIdentity:
    """Provide timing attribution fields used by the tracker."""

    source_key: str
    cube_alias: str


class _Clock:
    """Return deterministic millisecond timestamps for timing tests."""

    def __init__(self, values: list[float]) -> None:
        """Initialize with the timestamp sequence to return."""

        self._values = values
        self._last_value = values[-1]

    def __call__(self) -> float:
        """Return the next timestamp, then repeat the final value."""

        if self._values:
            self._last_value = self._values.pop(0)
        return self._last_value


def test_comfy_execution_timing_module_keeps_infrastructure_boundary() -> None:
    """Execution timing must not import Qt, presentation, or listener code."""

    source_path = (
        Path(__file__).parents[1]
        / "substitute"
        / "infrastructure"
        / "comfy"
        / "comfy_execution_timing.py"
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


def test_tracker_prefers_comfy_prompt_timestamps_and_sums_source_durations() -> None:
    """Comfy prompt timestamps and repeated source timings should be preserved."""

    tracker = ComfyExecutionTimingTracker(
        workflow_id="wf-1",
        prompt_id="pid-1",
        clock_ms=_Clock([10.0, 10.0, 250.0, 300.0, 810.0, 900.0]),
    )
    source = _SourceIdentity(source_key="wf-1:3", cube_alias="CubeA")

    tracker.mark_prompt_started(10000.0)
    tracker.mark_running(node_id="1", source_identity=source)
    tracker.mark_finished("1")
    tracker.mark_running(node_id="2", source_identity=source)
    tracker.mark_finished("2")
    tracker.mark_prompt_terminal(13080.0)
    tracker.finish_all(count_active_nodes=True)

    event = tracker.timing_event()

    assert event.job_duration_ms == 3080.0
    assert [
        (item.source_key, item.cube_alias, item.duration_ms)
        for item in event.cube_timings
    ] == [("wf-1:3", "CubeA", 750.0)]


def test_tracker_excludes_cached_and_failed_active_nodes() -> None:
    """Cached and failed nodes should not contribute cube execution timing."""

    tracker = ComfyExecutionTimingTracker(
        workflow_id="wf-1",
        prompt_id="pid-1",
        clock_ms=_Clock([1.0, 1.0, 2.0, 2.0, 3.0]),
    )
    source = _SourceIdentity(source_key="wf-1:3", cube_alias="CubeA")

    tracker.mark_cached("cached")
    tracker.mark_running(node_id="cached", source_identity=source)
    tracker.mark_finished("cached")
    tracker.mark_running(node_id="failed", source_identity=source)
    tracker.mark_failed("failed")
    tracker.finish_all(count_active_nodes=True)

    assert tracker.timing_event().cube_timings == ()


def test_tracker_uses_local_fallback_duration_when_prompt_timestamps_are_missing() -> (
    None
):
    """Local listener timing should supply job duration without Comfy timestamps."""

    tracker = ComfyExecutionTimingTracker(
        workflow_id="wf-1",
        prompt_id="pid-1",
        clock_ms=_Clock([1000.0, 1000.0, 2250.0, 2250.0]),
    )

    tracker.mark_running(
        node_id="1",
        source_identity=_SourceIdentity(source_key="wf-1:1", cube_alias="CubeA"),
    )
    tracker.finish_all(count_active_nodes=True)

    event = tracker.timing_event()

    assert event.job_duration_ms == 1250.0
    assert event.cube_timings[0].duration_ms == 1250.0


def test_tracker_discards_active_nodes_when_failure_timing_is_emitted() -> None:
    """Failure emission should preserve job timing without counting unfinished nodes."""

    tracker = ComfyExecutionTimingTracker(
        workflow_id="wf-1",
        prompt_id="pid-1",
        clock_ms=_Clock([1000.0, 1000.0, 1500.0]),
    )

    tracker.mark_running(
        node_id="1",
        source_identity=_SourceIdentity(source_key="wf-1:1", cube_alias="CubeA"),
    )
    tracker.finish_all(count_active_nodes=False)

    event = tracker.timing_event()

    assert event.job_duration_ms == 500.0
    assert event.cube_timings == ()


def test_timing_emitter_logs_and_invokes_callback_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Timing emission should be one-shot and include prompt-safe diagnostics."""

    events: list[GenerationExecutionTiming] = []
    tracker = ComfyExecutionTimingTracker(
        workflow_id="wf-1",
        prompt_id="pid-1",
        clock_ms=_Clock([1000.0, 1000.0, 1500.0, 1500.0]),
    )
    tracker.mark_running(
        node_id="1",
        source_identity=_SourceIdentity(source_key="wf-1:1", cube_alias="CubeA"),
    )
    emitter = ComfyExecutionTimingEmitter(
        tracker=tracker,
        on_timing=events.append,
    )

    with caplog.at_level(
        logging.INFO,
        logger="sugarsubstitute.infrastructure.comfy.comfy_execution_timing",
    ):
        emitter.emit_once(count_active_nodes=True)
        emitter.emit_once(count_active_nodes=True)

    assert len(events) == 1
    assert events[0].cube_timings[0].duration_ms == 500.0
    assert "Generation execution timing captured" in caplog.text
    assert "workflow_id=wf-1" in caplog.text
    assert "prompt_id=pid-1" in caplog.text
