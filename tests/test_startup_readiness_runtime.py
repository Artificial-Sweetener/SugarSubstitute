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

"""Tests for concrete startup readiness runtime adapters."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, cast

from substitute.app.bootstrap.startup_readiness_controller import (
    TimerSignalProtocol,
    StartupReadinessProbeProtocol,
    StartupRuntimeCompatibilityProbeProtocol,
)
from substitute.app.bootstrap.startup_readiness_runtime import (
    StartupReadinessRuntimeAdapters,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.execution import CancellationToken
from substitute.application.execution.executor import TaskRequest
from tests.execution_testing import ManualTaskHandle


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_READINESS_RUNTIME_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_readiness_runtime.py"
)
STARTUP_MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_STARTUP_READINESS_RUNTIME_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


class _Submitter:
    """Minimal submitter returned by the fake execution runtime."""

    def __init__(self) -> None:
        """Create empty route state."""

        self.closed = False

    def submit(
        self,
        request: TaskRequest[object],
        *,
        cancellation: CancellationToken,
    ) -> ManualTaskHandle[object]:
        """Return a manual handle for the supplied request."""

        _ = cancellation
        return ManualTaskHandle(request)

    def close(self) -> None:
        """Record closure."""

        self.closed = True


class _ExecutionRuntime:
    """Record startup submitter routes created by readiness adapters."""

    def __init__(self) -> None:
        """Create empty route records."""

        self.submitters: list[_Submitter] = []
        self.calls: list[tuple[str, str, object]] = []

    def submitter(self, name: str, *, owner_id: str, dispatcher: object) -> _Submitter:
        """Return a new fake submitter for one runtime route."""

        submitter = _Submitter()
        self.submitters.append(submitter)
        self.calls.append((name, owner_id, dispatcher))
        return submitter


def _adapters(
    *,
    startup_resources: StartupResourceRegistry | None = None,
    startup_timer: StartupTimer | None = None,
    timer_factory: Any | None = None,
    execution_runtime: _ExecutionRuntime | None = None,
) -> StartupReadinessRuntimeAdapters:
    """Create readiness adapters with fake execution collaborators."""

    return StartupReadinessRuntimeAdapters(
        startup_resources=startup_resources or StartupResourceRegistry(),
        startup_timer=startup_timer or StartupTimer(clock=_Clock()),
        execution_runtime=execution_runtime or _ExecutionRuntime(),
        execution_dispatcher_factory=lambda: object(),
        **({} if timer_factory is None else {"timer_factory": timer_factory}),
    )


def test_startup_readiness_runtime_retains_timer_and_marks_milestone() -> None:
    """Readiness runtime adapters should own timer retention and timing marks."""

    startup_timer = StartupTimer(clock=_Clock())
    timer = _Timer()
    adapters = _adapters(
        startup_timer=startup_timer,
        timer_factory=lambda: timer,
    )

    created_timer = adapters.create_readiness_timer()
    adapters.register_timer(created_timer)
    adapters.mark_startup_timer("comfy_http_ready")

    assert created_timer is cast(object, timer)
    assert adapters.readiness_timers() == (timer,)
    assert startup_timer.milestones()[0].name == "comfy_http_ready"


def test_startup_readiness_runtime_creates_probe_tasks() -> None:
    """Readiness runtime adapters should own concrete probe task construction."""

    runtime = _ExecutionRuntime()
    adapters = _adapters(execution_runtime=runtime)

    readiness_probe = adapters.create_readiness_probe(lambda _host, _port: True)
    compatibility_probe = adapters.create_runtime_compatibility_probe(lambda: None)

    assert readiness_probe.__class__.__name__ == "StartupReadinessProbe"
    assert compatibility_probe.__class__.__name__ == "StartupRuntimeCompatibilityProbe"
    assert [call[0] for call in runtime.calls] == ["startup", "startup"]
    cast(Any, readiness_probe).shutdown()
    cast(Any, compatibility_probe).shutdown()


def test_startup_readiness_runtime_registers_probe_resources() -> None:
    """Readiness runtime adapters should register startup-owned probes."""

    registry = StartupResourceRegistry()
    adapters = _adapters(
        startup_resources=registry,
    )
    readiness_probe = cast(StartupReadinessProbeProtocol, _Probe())
    compatibility_probe = cast(StartupRuntimeCompatibilityProbeProtocol, _Probe())

    adapters.register_readiness_probe(readiness_probe)
    adapters.register_runtime_compatibility_probe(compatibility_probe)

    assert registry.readiness_probes == [cast(object, readiness_probe)]
    assert registry.runtime_compatibility_probes == [cast(object, compatibility_probe)]


def test_startup_readiness_runtime_imports_no_forbidden_boundaries() -> None:
    """Readiness runtime adapters should not import presentation or IO layers."""

    imported_modules = _imported_module_names(STARTUP_READINESS_RUNTIME_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_READINESS_RUNTIME_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_readiness_runtime_adapters() -> None:
    """Startup should not keep local readiness runtime adapter closures."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = STARTUP_MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "StartupReadinessRuntimeAdapters(" not in source
    assert "StartupReadinessRuntimeAdapters(" in managed_ready_runtime_source
    assert "readiness_timers: list" not in source
    assert "def make_readiness_timer" not in source
    assert "def register_readiness_probe" not in source
    assert "def register_runtime_compatibility_probe" not in source
    assert "def mark_startup_timer" not in source
    assert "StartupReadinessProbe(" not in source
    assert "StartupRuntimeCompatibilityProbe(" not in source
    assert "create_readiness_probe" not in source
    assert "create_runtime_compatibility_probe" not in source
    assert "create_readiness_probe" in managed_ready_runtime_source
    assert "create_runtime_compatibility_probe" in managed_ready_runtime_source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert "managed_ready_runtime.bind_startup_readiness_controller(" not in source


def _imported_module_names(source_path: Path) -> set[str]:
    """Return module names imported by one Python source file."""

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


class _Timer:
    """Expose the timer methods required by readiness startup ports."""

    timeout: TimerSignalProtocol

    def __init__(self) -> None:
        """Create a timer double with an inert timeout signal."""

        self.timeout = _TimerSignal()

    def setInterval(self, _interval_ms: int) -> None:
        """Accept timer interval configuration."""

    def start(self) -> None:
        """Accept timer starts."""

    def stop(self) -> None:
        """Accept cleanup stop requests."""


class _TimerSignal:
    """Accept timeout callback connections."""

    def connect(self, _callback: object) -> None:
        """Accept one callback."""


class _Probe:
    """Expose probe resource methods required by startup cleanup."""

    def cancel_current(self) -> None:
        """Accept cancellation requests."""

    def shutdown(self) -> None:
        """Accept shutdown requests."""


class _Clock:
    """Return monotonically increasing fake timestamps."""

    def __init__(self) -> None:
        """Create a fake monotonic clock."""

        self.value = 0.0

    def __call__(self) -> float:
        """Return the next fake timestamp."""

        self.value += 0.1
        return self.value
