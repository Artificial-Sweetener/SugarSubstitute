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

"""Tests for startup ready-shell launch controller binding."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from substitute.app.bootstrap.ready_shell_controller import ReadyShellLaunchController
from substitute.app.bootstrap.managed_recovery_adapters import (
    ManagedRecoveryOutputStreamProtocol,
)
from substitute.app.bootstrap.ready_shell_state import create_ready_shell_state_bundle
from substitute.app.bootstrap.shell_reload_adapter import (
    ShellReloadAdapter,
    create_startup_shell_reload_state,
)
from substitute.app.bootstrap.startup_cancellation import (
    create_startup_cancellation_state,
)
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import StartupQtSchedulerPorts
from substitute.app.bootstrap.startup_ready_shell_launch import (
    create_startup_ready_shell_launch_controller,
    create_startup_ready_shell_launch_graph,
)
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_shutdown import StartupShutdownRuntime
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.app.bootstrap.lifecycle import (
    ManagedComfyCleanupOutcome,
    ManagedComfyCleanupResult,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_STARTUP_READY_SHELL_LAUNCH_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_create_startup_ready_shell_launch_controller_returns_controller() -> None:
    """Startup ready-shell launch binding should delegate controller construction."""

    controller = create_startup_ready_shell_launch_controller(
        no_comfy=False,
        startup_cancelled=lambda: False,
        shell_frame_present=lambda: False,
        splash=lambda: None,
        set_splash=lambda _splash: None,
        comfy_output_stream=object(),
        shutdown_request=object(),
        startup_timer=object(),
        runtime_services=object(),
        initial_shell_placement=None,
        initial_workspace=None,
        show_main_window=lambda **_kwargs: object(),
        attach_gui_reload_command=lambda _shell_frame: None,
        set_current_shell=lambda _shell_frame: None,
        launch_managed_ready_shell=lambda _context: None,
    )

    assert isinstance(controller, ReadyShellLaunchController)


def test_create_startup_ready_shell_launch_graph_returns_controller() -> None:
    """Startup ready-shell graph binding should build the controller graph."""

    ready_shell_state = create_ready_shell_state_bundle()
    shell_reload_state = create_startup_shell_reload_state()
    output_stream = cast(ManagedRecoveryOutputStreamProtocol, _OutputStream())
    shutdown_runtime = StartupShutdownRuntime(
        cleanup_handler=_cleanup_result,
    )
    shell_ports = StartupShellCompositionPorts(
        build_main_window=lambda **_kwargs: object(),
        show_main_window=lambda **_kwargs: object(),
        show_built_main_window=lambda _shell_frame, **_kwargs: _shell_frame,
        main_window_for_shell=lambda _shell_frame: object(),
        build_model_metadata_refresh_service=lambda _context: object(),
        is_comfy_http_ready=lambda _host, _port: False,
    )
    shell_reload_adapter = ShellReloadAdapter(
        main_window_for_shell=shell_ports.main_window_for_shell,
        build_main_window=shell_ports.build_main_window,
        show_built_main_window=shell_ports.show_built_main_window,
        comfy_runtime_actions_for=lambda _shell_frame: _RestartActions(),
        installation_context=object(),
        comfy_output_stream=output_stream,
        shutdown_request=lambda _shell_frame: None,
        startup_timer=StartupTimer(clock=_Clock()),
        runtime_services=object(),
        managed_comfy_lease=shutdown_runtime.managed_comfy_lease,
        restart_launch_command=("substitute",),
    )

    controller = create_startup_ready_shell_launch_graph(
        no_comfy=False,
        ready_shell_reference_state=ready_shell_state.reference_state,
        ready_shell_runtime_state=ready_shell_state.runtime_state,
        shell_reload_state=shell_reload_state,
        startup_cancellation_state=create_startup_cancellation_state(),
        shutdown_runtime=shutdown_runtime,
        shell_reload_adapter=shell_reload_adapter,
        shell_ports=shell_ports,
        managed_ready_ports=cast(StartupManagedReadyFactoryPorts, object()),
        startup_resources=StartupResourceRegistry(),
        startup_timer=StartupTimer(clock=_Clock()),
        startup_qt_schedulers=StartupQtSchedulerPorts(
            single_shot=lambda _delay_ms, _callback: None,
            visible_summary=lambda _callback: None,
        ),
        connect_cancel_request=lambda _callback: None,
        emit_splash_cancel=lambda: None,
        initial_splash_cancel_connector=None,
        startup_splash_start_or_adopt=lambda **_kwargs: object(),
        resolve_appearance=lambda: object(),
        comfy_output_stream=output_stream,
        request_shell_shutdown=lambda _shell_frame: None,
        quit_app=lambda: None,
        runtime_services=object(),
        initial_workspace=None,
        initial_shell_placement=None,
        provisional_restore_projection=None,
    )

    assert isinstance(controller, ReadyShellLaunchController)


def test_startup_ready_shell_launch_imports_no_forbidden_boundaries() -> None:
    """Ready-shell launch binding should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(STARTUP_READY_SHELL_LAUNCH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_READY_SHELL_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_startup_ready_shell_launch_binding() -> None:
    """Startup should not import the ready-shell controller directly."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_startup_ready_shell_launch_graph(" not in source
    assert "create_startup_ready_shell_launch_graph(" in shell_flow_source
    assert "create_startup_ready_shell_launch_controller(" not in source
    assert "create_startup_managed_ready_shell_launcher(" not in source
    assert (
        "launch_managed_ready_shell=managed_ready_shell_launcher.launch" not in source
    )
    assert "create_ready_shell_launch_controller(" not in source
    assert "from substitute.app.bootstrap.ready_shell_controller import" not in source


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


class _RestartActions:
    """Record Comfy restart handler installation in graph tests."""

    def set_comfy_restart_request_handler(self, handler: object) -> None:
        """Accept the restart handler without invoking it."""

        del handler


class _OutputStream:
    """Collect managed startup output lines in graph tests."""

    def __init__(self) -> None:
        """Create an empty output stream."""

        self.lines: list[str] = []

    def append_line(self, line: str) -> None:
        """Append one output line."""

        self.lines.append(line)


def _cleanup_result() -> ManagedComfyCleanupResult:
    """Return an inert cleanup result for graph tests."""

    return ManagedComfyCleanupResult(
        cleanup_ran=False,
        outcome=ManagedComfyCleanupOutcome.NO_ACTION_REQUIRED,
        managed_resource_present=False,
        live_process_present=False,
        metadata_present=False,
        used_persisted_metadata=False,
        termination_attempted=False,
        registry_cleared=False,
        pid=None,
        host=None,
        port=None,
        workspace=None,
        elapsed_ms=0,
        taskkill_timeout=False,
        verification_timeout=False,
        user_detail="",
        technical_detail="",
        diagnostic_detail="",
    )


class _Clock:
    """Deterministic monotonic clock for startup timer tests."""

    def __init__(self) -> None:
        """Create the test clock at zero."""

        self.current = 0.0

    def __call__(self) -> float:
        """Return the current timestamp."""

        return self.current
