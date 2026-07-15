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

"""Tests for fail-closed startup cleanup coordination."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from substitute.app.bootstrap.startup_failure_controller import (
    StartupFailClosedCleanupPortFactory,
    StartupFailClosedCleanupPorts,
    StartupFailureController,
    StartupManagedFailureReportAdapter,
    create_startup_fail_closed_cleanup_ports,
    create_startup_managed_failure_report_adapter,
    run_fail_closed_startup_cleanup,
)
from substitute.domain.comfy_startup_diagnostics import ComfyStartupIncident


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_FAILURE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_failure_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
FORBIDDEN_STARTUP_FAILURE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_fail_closed_cleanup_cancels_work_and_quits() -> None:
    """Fail-closed cleanup should stop startup work in the existing order."""

    calls: list[str] = []

    run_fail_closed_startup_cleanup(
        reason="startup_cancel",
        ports=StartupFailClosedCleanupPorts(
            readiness_timers=(_Timer("timer", calls),),
            runtime_compatibility_probes=(_RuntimeProbe("probe", calls),),
            stop_managed_comfy=lambda: calls.append("stop_comfy"),
            close_splash=lambda: calls.append("close_splash"),
            cleanup=lambda: calls.append("cleanup"),
            quit_app=lambda: calls.append("quit"),
            cancel_gui_queue=lambda: calls.append("cancel_queue"),
        ),
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == [
        "cancel_queue",
        "timer.stop",
        "probe.cancel_current",
        "stop_comfy",
        "close_splash",
        "cleanup",
        "quit",
    ]


def test_fail_closed_cleanup_allows_missing_gui_queue_cancel() -> None:
    """GUI task failure cleanup should not require queue cancellation."""

    calls: list[str] = []

    run_fail_closed_startup_cleanup(
        reason="gui_startup_failure",
        ports=StartupFailClosedCleanupPorts(
            readiness_timers=(),
            runtime_compatibility_probes=(),
            stop_managed_comfy=lambda: calls.append("stop_comfy"),
            close_splash=lambda: calls.append("close_splash"),
            cleanup=lambda: calls.append("cleanup"),
            quit_app=lambda: calls.append("quit"),
            cancel_gui_queue=None,
        ),
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == ["stop_comfy", "close_splash", "cleanup", "quit"]


def test_fail_closed_cleanup_preserves_quit_after_close_and_cleanup_errors() -> None:
    """Unexpected close and cleanup failures should not prevent app quit."""

    calls: list[str] = []

    def _raise_close() -> None:
        calls.append("close_splash")
        raise RuntimeError("close")

    def _raise_cleanup() -> None:
        calls.append("cleanup")
        raise RuntimeError("cleanup")

    run_fail_closed_startup_cleanup(
        reason="managed_startup_failure",
        ports=StartupFailClosedCleanupPorts(
            readiness_timers=(),
            runtime_compatibility_probes=(),
            stop_managed_comfy=lambda: calls.append("stop_comfy"),
            close_splash=_raise_close,
            cleanup=_raise_cleanup,
            quit_app=lambda: calls.append("quit"),
        ),
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == ["stop_comfy", "close_splash", "cleanup", "quit"]


def test_fail_closed_cleanup_ports_factory_adapts_current_startup_state() -> None:
    """Cleanup-port construction should own managed-stop and splash-close wiring."""

    calls: list[str] = []
    managed_state = _ManagedState(calls)
    splash = _Splash(calls)

    ports = create_startup_fail_closed_cleanup_ports(
        readiness_timers=(_Timer("timer", calls),),
        runtime_compatibility_probes=(_RuntimeProbe("probe", calls),),
        managed_comfy_state=managed_state,
        splash=splash,
        cleanup=lambda: calls.append("cleanup"),
        quit_app=lambda: calls.append("quit"),
        cancel_gui_queue=lambda: calls.append("cancel_queue"),
    )

    run_fail_closed_startup_cleanup(
        reason="startup_cancel",
        ports=ports,
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == [
        "cancel_queue",
        "timer.stop",
        "probe.cancel_current",
        "managed_state.request_stop",
        "splash.close",
        "cleanup",
        "quit",
    ]


def test_fail_closed_cleanup_ports_factory_allows_missing_state() -> None:
    """Cleanup-port construction should tolerate inactive managed Comfy and splash."""

    calls: list[str] = []
    ports = create_startup_fail_closed_cleanup_ports(
        readiness_timers=(),
        runtime_compatibility_probes=(),
        managed_comfy_state=None,
        splash=None,
        cleanup=lambda: calls.append("cleanup"),
        quit_app=lambda: calls.append("quit"),
    )

    run_fail_closed_startup_cleanup(
        reason="startup_cancel",
        ports=ports,
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == ["cleanup", "quit"]


def test_fail_closed_cleanup_port_factory_reads_live_startup_state() -> None:
    """Callable cleanup-port factory should read current startup state per request."""

    calls: list[str] = []
    readiness_timers: list[_Timer] = [_Timer("timer-a", calls)]
    runtime_probes: list[_RuntimeProbe] = [_RuntimeProbe("probe-a", calls)]
    managed_state: list[object | None] = [None]
    splash_state: list[_Splash | None] = [None]
    factory = StartupFailClosedCleanupPortFactory(
        readiness_timers=lambda: tuple(readiness_timers),
        runtime_compatibility_probes=lambda: tuple(runtime_probes),
        managed_comfy_state=lambda: managed_state[0],
        splash=lambda: splash_state[0],
        cleanup=lambda: calls.append("cleanup"),
        quit_app=lambda: calls.append("quit"),
        cancel_gui_queue=lambda: calls.append("cancel_queue"),
    )

    readiness_timers[:] = [_Timer("timer-b", calls)]
    runtime_probes[:] = [_RuntimeProbe("probe-b", calls)]
    managed_state[0] = _ManagedState(calls)
    splash_state[0] = _Splash(calls)
    ports = factory(cancel_gui_queue=True)

    run_fail_closed_startup_cleanup(
        reason="startup_cancel",
        ports=ports,
        close_failure_message="close failed",
        cleanup_failure_message="cleanup failed",
    )

    assert calls == [
        "cancel_queue",
        "timer-b.stop",
        "probe-b.cancel_current",
        "managed_state.request_stop",
        "splash.close",
        "cleanup",
        "quit",
    ]


def test_managed_failure_report_adapter_uses_live_transcript() -> None:
    """Managed failure report adapter should own report builder port assembly."""

    context = object()
    incident = _Incident()
    report = object()
    calls: list[dict[str, object]] = []

    def build_report(**kwargs: object) -> object:
        """Record managed failure report inputs."""

        calls.append(kwargs)
        return report

    adapter = StartupManagedFailureReportAdapter(
        installation_context=context,
        transcript=lambda: ("line",),
        build_report=build_report,
    )

    built_report = adapter.build(cast(ComfyStartupIncident, incident))

    assert built_report is report
    assert calls == [
        {
            "installation_context": context,
            "incident": incident,
            "transcript": ("line",),
        }
    ]


def test_create_startup_managed_failure_report_adapter_returns_adapter() -> None:
    """Managed failure report adapter construction should live in its owner."""

    adapter = create_startup_managed_failure_report_adapter(
        installation_context=object(),
        transcript=lambda: (),
        build_report=lambda **_kwargs: object(),
    )

    assert isinstance(adapter, StartupManagedFailureReportAdapter)


def test_startup_failure_controller_cancels_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup cancel should mark cancellation and skip duplicate cleanup."""

    events: list[str] = []
    trace_events: list[tuple[str, dict[str, object]]] = []
    cancelled = False

    def mark_cancelled() -> None:
        nonlocal cancelled
        cancelled = True

    monkeypatch.setattr(
        "substitute.app.bootstrap.startup_failure_controller.trace_mark",
        lambda event_name, **fields: trace_events.append((event_name, fields)),
    )
    controller = StartupFailureController(
        is_startup_cancelled=lambda: cancelled,
        mark_startup_cancelled=mark_cancelled,
        cleanup_ports=lambda **kwargs: _ports(events, **kwargs),
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: events.append("present"),
        quit_app=lambda: events.append("quit_app"),
    )

    controller.request_startup_cancel()
    controller.request_startup_cancel()

    assert cancelled is True
    assert events == ["cancel_queue", "stop_comfy", "close_splash", "cleanup", "quit"]
    assert trace_events[:2] == [
        ("startup.cancel.requested", {"route": "ready"}),
        (
            "startup.failure.cleanup.start",
            {
                "reason": "startup_cancel",
                "timer_count": 0,
                "runtime_compatibility_probe_count": 0,
                "gui_queue_cancelled": True,
            },
        ),
    ]
    assert trace_events[-1] == (
        "startup.cancel.skipped",
        {"reason": "already_cancelled"},
    )


def test_startup_failure_controller_handles_gui_task_failure() -> None:
    """GUI task failure should mark cancellation and run fail-closed cleanup."""

    events: list[str] = []
    cancelled = False

    def mark_cancelled() -> None:
        nonlocal cancelled
        cancelled = True

    controller = StartupFailureController(
        is_startup_cancelled=lambda: cancelled,
        mark_startup_cancelled=mark_cancelled,
        cleanup_ports=lambda **kwargs: _ports(events, **kwargs),
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=lambda _incident: object(),
        present_startup_failure_report=lambda _report: events.append("present"),
        quit_app=lambda: events.append("quit_app"),
    )

    controller.handle_gui_startup_failure("build_main_window")

    assert cancelled is True
    assert events == ["stop_comfy", "close_splash", "cleanup", "quit"]


def test_startup_failure_controller_handles_managed_failure() -> None:
    """Managed startup failure should clean up, present a report, then quit."""

    events: list[str] = []
    reports: list[object] = []
    incident = _Incident()
    report = object()
    cancelled = False

    def mark_cancelled() -> None:
        nonlocal cancelled
        cancelled = True

    def build_report(received: object) -> object:
        """Record the managed failure incident and return a report."""

        reports.append(received)
        return report

    controller = StartupFailureController(
        is_startup_cancelled=lambda: cancelled,
        mark_startup_cancelled=mark_cancelled,
        cleanup_ports=lambda **kwargs: _ports(events, **kwargs),
        trace_fields=lambda: {"route": "ready"},
        managed_failure_report_factory=build_report,
        present_startup_failure_report=lambda received: events.append(
            "present_report" if received is report else "present_wrong_report"
        ),
        quit_app=lambda: events.append("quit_app"),
    )

    controller.handle_managed_startup_failure(incident)

    assert cancelled is True
    assert reports == [incident]
    assert events == [
        "cancel_queue",
        "stop_comfy",
        "close_splash",
        "cleanup",
        "present_report",
        "quit_app",
    ]


def test_startup_failure_controller_imports_no_forbidden_boundaries() -> None:
    """Failure cleanup should stay independent from concrete UI and IO adapters."""

    imported_modules = _imported_module_names(STARTUP_FAILURE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_FAILURE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_repeated_fail_closed_cleanup() -> None:
    """Startup should delegate repeated fail-closed cleanup mechanics."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "managed_ready_launch.create_failure_queue(" in launch_source
    assert "managed_ready_runtime.create_failure_queue(" not in source
    assert "create_ready_shell_failure_queue(" not in source
    assert "ReadyShellFailureQueue(" not in source
    assert "StartupFailureController(" not in source
    assert "StartupFailClosedCleanupPortFactory(" not in source
    assert "GuiStartupTaskQueue(" not in source
    assert "def request_startup_cancel" not in source
    assert "def handle_gui_startup_failure" not in source
    assert "def handle_managed_startup_failure" not in source
    assert "def fail_closed_cleanup_ports" not in source
    assert "def stop_managed_comfy" not in source
    assert "def close_current_splash" not in source
    assert "create_startup_managed_failure_report_adapter(" not in source
    assert (
        "create_startup_managed_failure_report_adapter(" in managed_ready_runtime_source
    )
    assert "managed_ready_runtime.managed_failure_report_adapter" not in source
    assert "managed_ready_runtime.present_startup_failure_report" not in source
    assert "create_ready_shell_failure_queue(" in managed_ready_runtime_source
    assert "StartupManagedFailureReportAdapter(" not in source
    assert "build_startup_failure_report(" not in source
    assert "for timer in readiness_timers" not in source
    assert "runtime_probe.cancel_current()" not in source
    assert 'comfy_state["stop_event"].set()' not in source
    assert "ComfyStartupIncident" not in source


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
    """Record timer stop requests."""

    def __init__(self, name: str, calls: list[str]) -> None:
        """Create timer records."""

        self._name = name
        self._calls = calls

    def stop(self) -> None:
        """Record timer stop."""

        self._calls.append(f"{self._name}.stop")


class _RuntimeProbe:
    """Record runtime compatibility cancellation."""

    def __init__(self, name: str, calls: list[str]) -> None:
        """Create probe records."""

        self._name = name
        self._calls = calls

    def cancel_current(self) -> None:
        """Record cancellation."""

        self._calls.append(f"{self._name}.cancel_current")


class _ManagedState:
    """Record managed Comfy stop requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def request_stop(self, *, reason: str) -> None:
        """Record a cooperative stop request."""

        _ = reason
        self._calls.append("managed_state.request_stop")


class _Splash:
    """Record splash close requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store the call recorder."""

        self._calls = calls

    def close(self) -> None:
        """Record a splash close request."""

        self._calls.append("splash.close")


class _Incident:
    """Expose incident fields used for failure trace events."""

    kind = "process_exit"
    severity = "fatal"


def _ports(
    calls: list[str],
    *,
    cancel_gui_queue: bool,
    quit_app: Callable[[], None] | None = None,
) -> StartupFailClosedCleanupPorts:
    """Build recording cleanup ports for controller tests."""

    return StartupFailClosedCleanupPorts(
        readiness_timers=(),
        runtime_compatibility_probes=(),
        stop_managed_comfy=lambda: calls.append("stop_comfy"),
        close_splash=lambda: calls.append("close_splash"),
        cleanup=lambda: calls.append("cleanup"),
        quit_app=quit_app if quit_app is not None else lambda: calls.append("quit"),
        cancel_gui_queue=lambda: (
            calls.append("cancel_queue") if cancel_gui_queue else None
        ),
    )
