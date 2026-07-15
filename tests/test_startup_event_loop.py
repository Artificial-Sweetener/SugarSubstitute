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

"""Tests for startup event-loop shutdown orchestration."""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

import pytest

from substitute.app.bootstrap import startup_event_loop

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
EVENT_LOOP_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_event_loop.py"
)
FORBIDDEN_EVENT_LOOP_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_event_loop_runs_shutdown_sequence_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Event-loop owner should preserve the normal startup shutdown order."""

    calls: list[str] = []
    monkeypatch.setattr(
        startup_event_loop,
        "trace_mark",
        lambda name, **context: calls.append(f"trace:{name}:{context}"),
    )
    monkeypatch.setattr(
        startup_event_loop,
        "close_startup_trace",
        lambda: calls.append("close_trace"),
    )

    exit_code = startup_event_loop.run_startup_event_loop_and_shutdown(
        app=_App(calls, exit_code=7),
        splash=_Splash(calls),
        startup_resources=_StartupResources(calls),
        shutdown_runtime=_ShutdownRuntime(calls),
        shell_reload=_ShellReload(restart_requested=True),
        runtime_services=_RuntimeServices(calls),
        start_ready_app_process=lambda command: _record_launch(calls, command),
        keep_alive_references=(object(),),
    )

    assert exit_code == 7
    assert calls == [
        "runtime.register_shutdown_handlers",
        "trace:startup.event_loop.enter:{}",
        "app.exec",
        "trace:startup.event_loop.exit:{'exit_code': 7}",
        "splash.close",
        "resources.shutdown_all",
        "trace:startup.shutdown.cleanup.start:{}",
        "runtime.cleanup",
        "trace:startup.shutdown.cleanup.end:{}",
        "runtime.relaunch:True:python main.py",
        "launch:python main.py",
        "execution_runtime.shutdown",
        "close_trace",
        "resources.keep_alive_references",
    ]


def test_startup_event_loop_logs_splash_close_failure_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Splash close failures should not block cleanup or trace closure."""

    calls: list[str] = []
    logged_errors: list[str] = []
    monkeypatch.setattr(
        startup_event_loop,
        "trace_mark",
        lambda name, **context: calls.append(f"trace:{name}"),
    )
    monkeypatch.setattr(
        startup_event_loop,
        "close_startup_trace",
        lambda: calls.append("close_trace"),
    )
    monkeypatch.setattr(
        startup_event_loop,
        "log_exception",
        lambda _logger, message, **_context: logged_errors.append(message),
    )

    startup_event_loop.run_startup_event_loop_and_shutdown(
        app=_App(calls),
        splash=_Splash(calls, close_error=RuntimeError("close failed")),
        startup_resources=_StartupResources(calls),
        shutdown_runtime=_ShutdownRuntime(calls),
        shell_reload=_ShellReload(),
        runtime_services=_RuntimeServices(calls),
        start_ready_app_process=lambda command: _record_launch(calls, command),
    )

    assert "resources.shutdown_all" in calls
    assert "runtime.cleanup" in calls
    assert calls[-1] == "resources.keep_alive_references"
    assert logged_errors == ["Failed to close launch splash during shutdown"]


def test_startup_event_loop_imports_no_forbidden_boundaries() -> None:
    """Event-loop shutdown owner should stay free of concrete UI and process adapters."""

    imported_modules = _imported_module_names(EVENT_LOOP_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_EVENT_LOOP_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_event_loop_shutdown_sequence() -> None:
    """Startup should delegate event-loop and normal shutdown tail ownership."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "run_startup_event_loop_and_shutdown(" not in source
    assert "run_startup_event_loop_and_shutdown(" in shell_flow_source
    assert "app.exec()" not in source
    assert "shutdown_runtime.register_shutdown_handlers(" not in source
    assert "startup_resources.shutdown_all()" not in source
    assert "startup.shutdown.cleanup.start" not in source
    assert "close_startup_trace()" not in source


def _record_launch(calls: list[str], command: Sequence[str]) -> bool:
    """Record one ready-app launch request."""

    calls.append(f"launch:{' '.join(command)}")
    return True


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


class _App:
    """Record event-loop execution."""

    def __init__(self, calls: list[str], *, exit_code: int = 0) -> None:
        """Store call records and exit code."""

        self._calls = calls
        self._exit_code = exit_code

    def exec(self) -> int:
        """Record event-loop execution."""

        self._calls.append("app.exec")
        return self._exit_code


class _Splash:
    """Record launch splash closure."""

    def __init__(
        self,
        calls: list[str],
        *,
        close_error: Exception | None = None,
    ) -> None:
        """Store call records and optional close failure."""

        self._calls = calls
        self._close_error = close_error

    def close(self) -> None:
        """Record splash close and optionally fail."""

        self._calls.append("splash.close")
        if self._close_error is not None:
            raise self._close_error


class _StartupResources:
    """Record startup resource shutdown and retention."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    def shutdown_all(self) -> None:
        """Record resource shutdown."""

        self._calls.append("resources.shutdown_all")

    def keep_alive_references(self) -> tuple[object, ...]:
        """Record keep-alive reference collection."""

        self._calls.append("resources.keep_alive_references")
        return (object(),)


class _ShutdownRuntime:
    """Record shutdown runtime cleanup and relaunch requests."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    def cleanup(self) -> object:
        """Record managed cleanup."""

        self._calls.append("runtime.cleanup")
        return object()

    def register_shutdown_handlers(self, app: object) -> None:
        """Record shutdown-handler registration."""

        self._calls.append("runtime.register_shutdown_handlers")
        cast(_App, app)

    def relaunch_after_cleanup_if_requested(
        self,
        *,
        restart_requested: bool,
        restart_launch_command: Sequence[str],
        start_ready_app_process: Callable[[Sequence[str]], bool],
    ) -> None:
        """Record relaunch coordination and delegate to the launch port."""

        self._calls.append(
            f"runtime.relaunch:{restart_requested}:{' '.join(restart_launch_command)}"
        )
        if restart_requested:
            start_ready_app_process(restart_launch_command)


class _ShellReload:
    """Expose GUI reload relaunch state."""

    def __init__(self, *, restart_requested: bool = False) -> None:
        """Store restart request state."""

        self._restart_requested = restart_requested

    @property
    def restart_after_cleanup_requested(self) -> bool:
        """Return whether relaunch was requested."""

        return self._restart_requested

    @property
    def restart_launch_command(self) -> Sequence[str]:
        """Return the relaunch command."""

        return ("python", "main.py")


class _ExecutionRuntime:
    """Record execution runtime shutdown."""

    def __init__(self, calls: list[str]) -> None:
        """Store call records."""

        self._calls = calls

    def shutdown(self) -> None:
        """Record execution runtime shutdown."""

        self._calls.append("execution_runtime.shutdown")


class _RuntimeServices:
    """Expose runtime services needed by event-loop shutdown."""

    def __init__(self, calls: list[str]) -> None:
        """Create the execution runtime fake."""

        self.execution_runtime = _ExecutionRuntime(calls)


def _assert_protocol_shapes() -> None:
    """Type-check fake objects against event-loop protocols."""

    calls: list[str] = []
    cast(startup_event_loop.StartupApplicationProtocol, _App(calls))
    cast(startup_event_loop.StartupSplashProtocol, _Splash(calls))
    cast(startup_event_loop.StartupResourceRegistryProtocol, _StartupResources(calls))
    cast(startup_event_loop.StartupShutdownRuntimeProtocol, _ShutdownRuntime(calls))
    cast(startup_event_loop.StartupShellReloadProtocol, _ShellReload())
    cast(startup_event_loop.StartupRuntimeServicesProtocol, _RuntimeServices(calls))
    cast(Any, calls)
