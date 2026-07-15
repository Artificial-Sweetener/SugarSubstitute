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

"""Tests for startup readiness and compatibility probe tasks."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeVar, cast

from substitute.app.bootstrap import startup_probe_tasks
from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.execution_testing import ManualTaskHandle
from substitute.application.backend_compatibility import (
    BackendCompatibilityResult,
    RuntimeCompatibilityStatus,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBE_TASKS_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_probe_tasks.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
TResult = TypeVar("TResult")


class _QueuedSubmitter:
    """Deterministically queue execution tasks for startup probe tests."""

    def __init__(self) -> None:
        self.requests: list[TaskRequest[object]] = []
        self.handles: list[ManualTaskHandle[object]] = []
        self.cancellations: list[CancellationToken] = []
        self.closed = False

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[TResult]:
        """Queue one task request and return a manual handle."""

        handle: ManualTaskHandle[TResult] = ManualTaskHandle(request)
        self.requests.append(cast(TaskRequest[object], request))
        self.handles.append(cast(ManualTaskHandle[object], handle))
        self.cancellations.append(cancellation)
        return handle

    def close(self) -> None:
        """Record submitter closure."""

        self.closed = True

    def run_next(self) -> None:
        """Run and complete the next queued task."""

        request = self.requests.pop(0)
        handle = self.handles.pop(0)
        cancellation = self.cancellations.pop(0)
        result = request.work(cancellation)
        handle.complete_success(result)


def _imported_modules(source: str) -> set[str]:
    """Return top-level imported module names from one Python source string."""

    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_startup_readiness_probe_runs_probe_off_request_call() -> None:
    """Readiness probe requests should submit tasks without probing inline."""

    submitter = _QueuedSubmitter()
    probe_calls: list[tuple[str, int]] = []
    results: list[startup_probe_tasks.ReadinessProbeResult] = []

    def record_probe(host: str, port: int) -> bool:
        """Record one fake readiness probe and report ready."""

        probe_calls.append((host, port))
        return True

    readiness_probe = startup_probe_tasks.StartupReadinessProbe(
        probe=record_probe,
        submitter=submitter,
        close_submitter=submitter.close,
    )
    readiness_probe.connect_finished(results.append)

    request_id = readiness_probe.request_probe(host="127.0.0.1", port=8188)

    assert request_id == 1
    assert probe_calls == []
    assert readiness_probe.request_probe(host="127.0.0.1", port=8188) is None

    submitter.run_next()

    assert probe_calls == [("127.0.0.1", 8188)]
    assert results == [
        startup_probe_tasks.ReadinessProbeResult(
            request_id=1,
            host="127.0.0.1",
            port=8188,
            ready=True,
        )
    ]
    assert readiness_probe.accept_result(results[0]) is True
    assert readiness_probe.request_probe(host="127.0.0.1", port=8188) == 2

    readiness_probe.shutdown()
    assert submitter.closed is True


def test_startup_readiness_probe_ignores_cancelled_result() -> None:
    """Cancelled readiness probe results should not be accepted as current."""

    submitter = _QueuedSubmitter()
    results: list[startup_probe_tasks.ReadinessProbeResult] = []
    readiness_probe = startup_probe_tasks.StartupReadinessProbe(
        probe=lambda _host, _port: True,
        submitter=submitter,
        close_submitter=submitter.close,
    )
    readiness_probe.connect_finished(results.append)

    assert readiness_probe.request_probe(host="127.0.0.1", port=8188) == 1
    readiness_probe.cancel_current()
    late_result = startup_probe_tasks.ReadinessProbeResult(
        request_id=1,
        host="127.0.0.1",
        port=8188,
        ready=True,
    )

    assert readiness_probe.accept_result(late_result) is False
    assert results == []
    readiness_probe.shutdown()


def test_startup_runtime_compatibility_probe_runs_assessment_off_request_call() -> None:
    """Compatibility probe requests should submit tasks without assessing inline."""

    submitter = _QueuedSubmitter()
    assess_calls = 0
    results: list[startup_probe_tasks.RuntimeCompatibilityProbeResult] = []
    compatibility = BackendCompatibilityResult(
        status=RuntimeCompatibilityStatus.COMPATIBLE,
        summary="Compatible.",
        installed_backend_version="1.6.2",
        required_backend_version=">=1.6.2,<2.0.0",
        installed_sugarcubes_version="0.10.0",
        required_sugarcubes_version=">=0.10.0,<2.0.0",
        repairable=False,
    )

    def assess() -> BackendCompatibilityResult:
        """Record one fake compatibility assessment."""

        nonlocal assess_calls
        assess_calls += 1
        return compatibility

    compatibility_probe = startup_probe_tasks.StartupRuntimeCompatibilityProbe(
        assess=assess,
        submitter=submitter,
        close_submitter=submitter.close,
    )
    compatibility_probe.connect_finished(results.append)

    request_id = compatibility_probe.request_assessment()

    assert request_id == 1
    assert assess_calls == 0
    assert compatibility_probe.request_assessment() is None

    submitter.run_next()

    assert assess_calls == 1
    assert results == [
        startup_probe_tasks.RuntimeCompatibilityProbeResult(
            request_id=1,
            compatibility=compatibility,
        )
    ]
    assert compatibility_probe.accept_result(results[0]) is True
    assert compatibility_probe.request_assessment() == 2

    compatibility_probe.shutdown()
    assert submitter.closed is True


def test_startup_runtime_compatibility_probe_ignores_cancelled_result() -> None:
    """Cancelled compatibility probe results should not be accepted as current."""

    submitter = _QueuedSubmitter()
    results: list[startup_probe_tasks.RuntimeCompatibilityProbeResult] = []
    compatibility_probe = startup_probe_tasks.StartupRuntimeCompatibilityProbe(
        assess=lambda: None,
        submitter=submitter,
        close_submitter=submitter.close,
    )
    compatibility_probe.connect_finished(results.append)

    assert compatibility_probe.request_assessment() == 1
    compatibility_probe.cancel_current()
    late_result = startup_probe_tasks.RuntimeCompatibilityProbeResult(
        request_id=1,
        compatibility=None,
    )

    assert compatibility_probe.accept_result(late_result) is False
    assert results == []
    compatibility_probe.shutdown()


def test_startup_probe_tasks_keep_execution_boundaries() -> None:
    """Keep startup probe tasks out of presentation and infrastructure layers."""

    imports = _imported_modules(PROBE_TASKS_SOURCE.read_text(encoding="utf-8"))

    assert "subprocess" not in imports
    assert "qfluentwidgets" not in imports
    assert "qframelesswindow" not in imports
    assert all(not module.startswith("substitute.presentation") for module in imports)
    assert all(not module.startswith("substitute.infrastructure") for module in imports)


def test_startup_facade_no_longer_owns_probe_tasks() -> None:
    """Keep task single-flight state out of the startup facade."""

    startup_source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "class _StartupReadinessProbe" not in startup_source
    assert "class _StartupRuntimeCompatibilityProbe" not in startup_source
    assert "class _ReadinessProbeResult" not in startup_source
    assert "class _RuntimeCompatibilityProbeResult" not in startup_source
    assert "class _ReadinessProbeBridge" not in startup_source
    assert "class _RuntimeCompatibilityProbeBridge" not in startup_source
