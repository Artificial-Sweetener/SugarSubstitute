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

"""Tests for startup shell runtime graph composition."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from substitute.app.bootstrap import startup_shell_runtime
from substitute.app.bootstrap.ready_shell_state import ReadyShellRuntimeState
from substitute.app.bootstrap.startup_ports import StartupShellCompositionPorts
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime

PROJECT_ROOT = Path(__file__).resolve().parents[4]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_SHELL_RUNTIME_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_runtime.py"
)
FORBIDDEN_SHELL_RUNTIME_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "subprocess",
)


def test_create_startup_shell_runtime_graph_wires_shutdown_and_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shell runtime graph should compose shutdown and reload collaborators."""

    app = _App()
    managed_lease = object()
    shell_reload_state = _ShellReloadState()
    runtime_state = ReadyShellRuntimeState(comfy_state="managed")
    shell_ports = StartupShellCompositionPorts(
        build_main_window=lambda **_kwargs: object(),
        show_main_window=lambda **_kwargs: object(),
        show_built_main_window=lambda _shell_frame, **_kwargs: _shell_frame,
        main_window_for_shell=lambda _shell_frame: object(),
        build_model_metadata_refresh_service=(
            lambda _context, _prepared_caches: object()
        ),
        is_comfy_http_ready=lambda _host, _port: False,
    )
    shutdown_runtime_obj = _ShutdownRuntime(managed_lease=managed_lease)
    shutdown_runtime = cast(StartupShutdownRuntime, shutdown_runtime_obj)

    def request_shell_shutdown(_shell_frame: object | None) -> None:
        """Accept shell shutdown requests."""

    shell_reload_adapter = object()
    execution_runtime = object()
    finalization_service = SimpleNamespace(persist=lambda _prepared: object())
    session_persistence_submitter = object()
    runtime_services = SimpleNamespace(
        execution_runtime=execution_runtime,
        session_finalization_service=finalization_service,
        session_persistence_submitter=session_persistence_submitter,
    )
    shutdown_calls: list[dict[str, object]] = []
    request_port_calls: list[dict[str, object]] = []
    reload_calls: list[dict[str, object]] = []
    session_adapter_calls: list[dict[str, object]] = []
    operation_calls: list[dict[str, object]] = []

    class _SessionAdapter:
        """Expose terminal session ports for graph wiring."""

        def prepare_shutdown(self, _source_shell: object | None) -> object:
            """Prepare one fake shutdown save."""

            return object()

        def begin_gui_reload(self, _main_window: object) -> object:
            """Begin one fake GUI reload save."""

            return object()

    session_adapter = _SessionAdapter()

    class _ShutdownOperation:
        """Expose composed shutdown preparation and work ports."""

        def prepare(self) -> None:
            """Accept preparation."""

        def run(self) -> object:
            """Accept detached cleanup."""

            return object()

    shutdown_operation = _ShutdownOperation()

    def fake_shutdown_runtime(**kwargs: object) -> StartupShutdownRuntime:
        """Record process-manager shutdown runtime construction."""

        shutdown_calls.append(kwargs)
        return shutdown_runtime

    def fake_request_ports(**kwargs: object) -> object:
        """Record shutdown request port construction."""

        request_port_calls.append(kwargs)
        return _ShutdownRequestPorts(request_shell_shutdown)

    def fake_reload_adapter(**kwargs: object) -> object:
        """Record bound shell reload construction."""

        reload_calls.append(kwargs)
        return shell_reload_adapter

    def fake_session_adapter(**kwargs: object) -> object:
        """Record active-shell finalization adapter construction."""

        session_adapter_calls.append(kwargs)
        return session_adapter

    def fake_shutdown_operation(**kwargs: object) -> object:
        """Record composed shutdown operation construction."""

        operation_calls.append(kwargs)
        return shutdown_operation

    monkeypatch.setattr(
        startup_shell_runtime,
        "create_process_manager_startup_shutdown_runtime",
        fake_shutdown_runtime,
    )
    monkeypatch.setattr(
        startup_shell_runtime,
        "create_startup_shutdown_request_ports",
        fake_request_ports,
    )
    monkeypatch.setattr(
        startup_shell_runtime,
        "create_bound_shell_reload_adapter",
        fake_reload_adapter,
    )
    monkeypatch.setattr(
        startup_shell_runtime,
        "ShellSessionFinalizationAdapter",
        fake_session_adapter,
    )
    monkeypatch.setattr(
        startup_shell_runtime,
        "ShutdownFinalizationOperation",
        fake_shutdown_operation,
    )

    graph = startup_shell_runtime.create_startup_shell_runtime_graph(
        app=app,
        ready_shell_runtime_state=runtime_state,
        shell_reload_state=cast(Any, shell_reload_state),
        shell_ports=shell_ports,
        installation_context="context",
        comfy_output_stream="stream",
        startup_timer="timer",
        runtime_services=runtime_services,
        restart_launch_command=("python", "main.py"),
    )

    assert graph.shutdown_runtime is shutdown_runtime
    assert graph.request_shell_shutdown is request_shell_shutdown
    assert graph.shell_reload_adapter is shell_reload_adapter
    assert len(shutdown_calls) == 1
    comfy_state_getter = cast(
        Callable[[], object], shutdown_calls[0]["comfy_state_getter"]
    )
    assert comfy_state_getter() == "managed"
    assert session_adapter_calls == [
        {
            "current_shell": session_adapter_calls[0]["current_shell"],
            "main_window_for_shell": shell_ports.main_window_for_shell,
        }
    ]
    assert operation_calls == [
        {
            "prepare_session": session_adapter.prepare_shutdown,
            "persist_session": finalization_service.persist,
            "cleanup_managed_comfy": shutdown_runtime_obj.cleanup,
        }
    ]
    assert request_port_calls == [
        {
            "app": app,
            "cleanup": shutdown_operation.run,
            "before_cleanup": shutdown_operation.prepare,
            "cleanup_bypass": shutdown_runtime_obj.cleanup_bypass,
            "cleanup_submitter": session_persistence_submitter,
        }
    ]
    assert reload_calls == [
        {
            "state": shell_reload_state,
            "main_window_for_shell": shell_ports.main_window_for_shell,
            "build_main_window": shell_ports.build_main_window,
            "show_built_main_window": shell_ports.show_built_main_window,
            "comfy_runtime_actions_for": reload_calls[0]["comfy_runtime_actions_for"],
            "installation_context": "context",
            "comfy_output_stream": "stream",
            "shutdown_request": request_shell_shutdown,
            "startup_timer": "timer",
            "runtime_services": runtime_services,
            "managed_comfy_lease": managed_lease,
            "begin_session_finalization": session_adapter.begin_gui_reload,
            "restart_launch_command": ("python", "main.py"),
        }
    ]


def test_startup_shell_runtime_imports_no_forbidden_boundaries() -> None:
    """Shell runtime graph should avoid shell execution dependencies."""

    imported_modules = _imported_module_names(STARTUP_SHELL_RUNTIME_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SHELL_RUNTIME_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shell_runtime_graph() -> None:
    """Startup should request the shell runtime graph instead of wiring it inline."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_shell_runtime_graph(" in source
    assert "create_process_manager_startup_shutdown_runtime(" not in source
    assert "create_startup_shutdown_request_ports(" not in source
    assert "create_bound_shell_reload_adapter(" not in source
    assert "comfy_runtime_actions_for" not in source


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


class _ShutdownRuntime:
    """Expose the managed lease expected by shell runtime graph composition."""

    def __init__(self, *, managed_lease: object) -> None:
        """Store the fake managed lease."""

        self.managed_comfy_lease = managed_lease
        self.cleanup_bypass = None

    def cleanup(self) -> object:
        """Return one fake managed cleanup result."""

        return object()


class _App:
    """Application test double with the shutdown app port."""

    def quit(self) -> None:
        """Accept application quit requests."""


class _ShutdownRequestPorts:
    """Expose the shutdown request port expected by the graph."""

    def __init__(
        self,
        request_shell_shutdown: Callable[[object | None], None],
    ) -> None:
        """Store the fake shutdown request."""

        self.request_shell_shutdown = request_shell_shutdown


class _ShellReloadState:
    """Expose shell reload state ports used by graph composition."""

    def __init__(self) -> None:
        """Initialize callback counters."""

        self.shell_frame = object()
