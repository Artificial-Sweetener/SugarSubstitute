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

"""Verify hidden editor build scheduler behavior and ownership boundaries."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pytest

import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
from substitute.presentation.editor.panel.hidden_build_scheduler import (
    HiddenBuildScheduler,
    HiddenBuildSchedulerPorts,
)
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from tests.editor_projection_test_helpers import _TimerQueue


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "hidden_build_scheduler.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


class _StepSession:
    """Return scripted completion values for projected build tests."""

    def __init__(
        self,
        step_results: Sequence[bool],
        *,
        first_usable_after: int = 1,
    ) -> None:
        """Store scripted step results and first-usable threshold."""

        self.step_results = list(step_results)
        self.step_calls = 0
        self._first_usable_after = first_usable_after

    def step(self) -> bool:
        """Return the next scripted completion state."""

        self.step_calls += 1
        if not self.step_results:
            return True
        return self.step_results.pop(0)

    @property
    def first_usable_reached(self) -> bool:
        """Return whether the scripted session has reached first usable state."""

        return self.step_calls >= self._first_usable_after


def _projected_build(
    cube_alias: str, session: object, token: object
) -> ProjectedCubeBuild:
    """Create a projected build DTO for scheduler tests."""

    return ProjectedCubeBuild(
        cube_alias=cube_alias,
        final_widget=object(),
        build_session=session,
        started_at=0.0,
        token=token,
    )


def _scheduler(
    *,
    revealed: list[tuple[str, ...]] | None = None,
    completed: list[tuple[str, object]] | None = None,
    failed: list[tuple[str, object, str]] | None = None,
) -> HiddenBuildScheduler:
    """Create a scheduler with recording ports."""

    revealed = revealed if revealed is not None else []
    completed = completed if completed is not None else []
    failed = failed if failed is not None else []

    def reveal(builds: Sequence[ProjectedCubeBuild], workflow_id: str) -> None:
        """Record a completed reveal batch."""

        revealed.append(tuple(build.cube_alias for build in builds) + (workflow_id,))

    def mark_complete(cube_alias: str, token: object) -> None:
        """Record build completion."""

        completed.append((cube_alias, token))

    def mark_failed(cube_alias: str, token: object, error: object) -> None:
        """Record build failure."""

        failed.append((cube_alias, token, type(error).__name__))

    return HiddenBuildScheduler(
        HiddenBuildSchedulerPorts(
            reveal_projected_cube_builds=reveal,
            mark_build_complete=mark_complete,
            mark_build_failed=mark_failed,
        )
    )


def _patch_timer(
    monkeypatch: pytest.MonkeyPatch,
    timer_queue: _TimerQueue,
) -> None:
    """Route scheduler timer callbacks through a deterministic queue."""

    timer = cast(Any, getattr(hidden_build_scheduler, "QTimer"))
    monkeypatch.setattr(
        timer,
        "singleShot",
        staticmethod(timer_queue.singleShot),
    )


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_schedule_projected_cube_builds_reveals_batch_after_all_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projected build scheduling should reveal and complete finished batches once."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    revealed: list[tuple[str, ...]] = []
    completed: list[tuple[str, object]] = []
    scheduler = _scheduler(revealed=revealed, completed=completed)
    first_token = object()
    second_token = object()
    completions: list[str] = []
    cancellations: list[str] = []

    scheduler.schedule_projected_cube_builds(
        [
            _projected_build("A", _StepSession([True]), first_token),
            _projected_build("B", _StepSession([True]), second_token),
        ],
        on_complete=lambda: completions.append("complete"),
        on_cancel=lambda: cancellations.append("cancel"),
        workflow_id="workflow-a",
        is_current=lambda: True,
    )
    timer_queue.run_all()

    assert revealed == [("A", "B", "workflow-a")]
    assert completed == [("A", first_token), ("B", second_token)]
    assert completions == ["complete"]
    assert cancellations == []


def test_schedule_projected_cube_builds_defers_to_visible_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A false visible commit result should keep scheduler completion deferred."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    scheduler = _scheduler()
    visible_batches: list[tuple[str, ...]] = []
    completions: list[str] = []

    def visible_commit(builds: Sequence[ProjectedCubeBuild]) -> bool:
        """Record visible-commit delegation and request deferral."""

        visible_batches.append(tuple(build.cube_alias for build in builds))
        return False

    scheduler.schedule_projected_cube_builds(
        [_projected_build("A", _StepSession([True]), object())],
        on_complete=lambda: completions.append("complete"),
        on_cancel=lambda: None,
        workflow_id="workflow-a",
        visible_commit=visible_commit,
    )
    timer_queue.run_all()

    assert visible_batches == [("A",)]
    assert completions == []


def test_schedule_projected_cube_builds_records_individual_build_completion_timing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reveals should receive timing captured when each staged build finishes."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    scheduler = _scheduler()
    revealed_builds: list[ProjectedCubeBuild] = []

    def visible_commit(builds: Sequence[ProjectedCubeBuild]) -> bool:
        """Capture the scheduler-completed build records for inspection."""

        revealed_builds.extend(builds)
        return True

    scheduler.schedule_projected_cube_builds(
        [_projected_build("A", _StepSession([True]), object())],
        on_complete=lambda: None,
        on_cancel=lambda: None,
        workflow_id="workflow-a",
        visible_commit=visible_commit,
    )
    timer_queue.run_all()

    assert len(revealed_builds) == 1
    assert isinstance(revealed_builds[0].build_elapsed_ms, float)
    assert isinstance(revealed_builds[0].completed_at, float)


def test_schedule_projected_cube_builds_marks_failure_and_cancels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expected step failures should mark the active build failed and cancel."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    failed: list[tuple[str, object, str]] = []
    scheduler = _scheduler(failed=failed)
    token = object()
    cancellations: list[str] = []

    class _FailingSession:
        """Raise from the projected step method."""

        def step(self) -> bool:
            """Raise an expected scheduler failure."""

            raise RuntimeError("boom")

    scheduler.schedule_projected_cube_builds(
        [_projected_build("A", _FailingSession(), token)],
        on_complete=lambda: None,
        on_cancel=lambda: cancellations.append("cancel"),
        workflow_id="workflow-a",
    )
    timer_queue.run_all()

    assert failed == [("A", token, "RuntimeError")]
    assert cancellations == ["cancel"]


def test_schedule_cube_build_session_reports_first_usable_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incremental session scheduling should report first usable before final done."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    session = _StepSession([False, True], first_usable_after=1)
    calls: list[str] = []

    HiddenBuildScheduler.schedule_cube_build_session(
        session,
        on_first_usable=lambda: calls.append("first"),
        on_complete=lambda: calls.append("complete"),
        is_current=lambda: True,
    )
    timer_queue.run_all()

    assert calls == ["first", "complete"]
    assert session.step_calls == 2


def test_schedule_cube_build_session_cancels_before_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale incremental sessions should cancel without running a build step."""

    timer_queue = _TimerQueue()
    _patch_timer(monkeypatch, timer_queue)
    session = _StepSession([True])
    calls: list[str] = []

    HiddenBuildScheduler.schedule_cube_build_session(
        session,
        on_complete=lambda: calls.append("complete"),
        is_current=lambda: False,
        on_cancel=lambda: calls.append("cancel"),
    )
    timer_queue.run_all()

    assert calls == ["cancel"]
    assert session.step_calls == 0


def test_hidden_build_scheduler_owns_timer_boundary() -> None:
    """Scheduler should own QTimer use without importing coordinator or Fluent code."""

    scheduler_imports = _imported_module_names(SCHEDULER_SOURCE)
    coordinator_imports = _imported_module_names(COORDINATOR_SOURCE)
    coordinator_source = COORDINATOR_SOURCE.read_text(encoding="utf-8")

    assert "PySide6.QtCore" in scheduler_imports
    assert "PySide6.QtCore" not in coordinator_imports
    assert "QTimer" not in coordinator_source
    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in scheduler_imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_projection_coordinator_no_longer_defines_scheduler_methods() -> None:
    """Moved scheduler methods should not return to the coordinator monolith."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "EditorHiddenBuildAndInsertPipeline" not in class_methods
    assert "_schedule_projected_cube_builds" not in coordinator_methods
    assert "_commit_scheduled_builds" not in coordinator_methods
    assert "_schedule_cube_build_session" not in coordinator_methods
