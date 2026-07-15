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

"""Tests for startup shell-flow composition."""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.app.bootstrap import startup_shell_flow
from substitute.app.bootstrap.bootstrap_route_controller import (
    BootstrapRouteWindowProtocol,
)
from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.ready_shell_state import create_ready_shell_state_bundle
from substitute.app.bootstrap.shell_reload_adapter import (
    create_startup_shell_reload_state,
)
from substitute.app.bootstrap.startup_cancellation import (
    create_startup_cancellation_state,
)
from substitute.app.bootstrap.startup_cli import StartupReadyAppLaunch
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import StartupQtSchedulerPorts
from substitute.app.bootstrap.startup_resources import StartupResourceRegistry
from substitute.app.bootstrap.startup_route_flow import StartupRouteFlowResult
from substitute.app.bootstrap.startup_shell_flow import run_startup_shell_flow
from substitute.app.bootstrap.startup_shell_runtime import StartupShellRuntimeGraph
from substitute.app.bootstrap.startup_support_graph import StartupSupportGraph
from substitute.app.bootstrap.startup_timing import StartupTimer
from substitute.application.workspace_state import InitialWorkspaceRestorePlan
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyTargetConfiguration,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
FORBIDDEN_SHELL_FLOW_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "subprocess",
    "substitute.infrastructure",
    "substitute.presentation",
)


def test_run_startup_shell_flow_routes_and_runs_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Shell flow should wire launch graph, route dispatch, and event-loop handoff."""

    calls: list[str] = []
    initial_splash = cast(LaunchSplashClient, _Splash())
    replacement_splash = cast(LaunchSplashClient, _Splash())
    onboarding_window = object()
    shell_frame = object()
    app = _App()
    ready_shell_state = create_ready_shell_state_bundle(initial_splash=initial_splash)
    shell_reload_state = create_startup_shell_reload_state()
    shell_reload_state.set_shell_frame(shell_frame)
    cancel_signal = _CancelSignal(calls)
    shell_reload = _ShellReload()
    shutdown_runtime = object()
    request_shell_shutdown = object()
    runtime_services = _RuntimeServices()
    ready_app_launch = StartupReadyAppLaunch(
        entrypoint_path=tmp_path / "main.py",
        restart_launch_command=["python", "main.py"],
    )
    initial_restore_plan = InitialWorkspaceRestorePlan(
        workspace=None,
        shell_placement=None,
        warnings=(),
        provisional_restore_projection=None,
    )
    support_graph = cast(
        StartupSupportGraph,
        SimpleNamespace(
            ready_shell_state=ready_shell_state,
            shell_reload_state=shell_reload_state,
            startup_splash_ports=SimpleNamespace(
                start_or_adopt_launch_splash=lambda **_kwargs: replacement_splash,
            ),
            startup_cancel_bridge=SimpleNamespace(cancel_requested=cancel_signal),
            startup_cancellation_state=create_startup_cancellation_state(),
            startup_qt_schedulers=StartupQtSchedulerPorts(
                single_shot=lambda _delay_ms, _callback: None,
                visible_summary=lambda _callback: None,
            ),
            shell_ports=cast(StartupShellCompositionPorts, object()),
            managed_ready_ports=cast(StartupManagedReadyFactoryPorts, object()),
        ),
    )
    shell_runtime_graph = cast(
        StartupShellRuntimeGraph,
        SimpleNamespace(
            shutdown_runtime=shutdown_runtime,
            request_shell_shutdown=request_shell_shutdown,
            shell_reload_adapter=shell_reload,
        ),
    )
    launch_controller = SimpleNamespace(
        launch=lambda context: calls.append(
            f"launch:{context.installation.installation_root.name}"
        )
    )
    resolved_appearance = object()

    def create_launch_graph(**kwargs: object) -> object:
        """Record ready-shell launch graph wiring."""

        calls.append("create_launch_graph")
        assert (
            kwargs["ready_shell_reference_state"] is ready_shell_state.reference_state
        )
        assert kwargs["ready_shell_runtime_state"] is ready_shell_state.runtime_state
        assert kwargs["shell_reload_state"] is shell_reload_state
        assert kwargs["shutdown_runtime"] is shutdown_runtime
        assert kwargs["shell_reload_adapter"] is shell_reload
        assert kwargs["request_shell_shutdown"] is request_shell_shutdown
        assert kwargs["initial_workspace"] is initial_restore_plan.workspace
        assert kwargs["initial_shell_placement"] is initial_restore_plan.shell_placement
        assert (
            kwargs["provisional_restore_projection"]
            is initial_restore_plan.provisional_restore_projection
        )
        assert cast(Callable[[], object], kwargs["resolve_appearance"])() is (
            resolved_appearance
        )
        cast(Callable[[Callable[[], None]], object], kwargs["connect_cancel_request"])(
            lambda: calls.append("cancel_callback")
        )
        cast(Callable[[], None], kwargs["emit_splash_cancel"])()
        return launch_controller

    def route_flow(**kwargs: object) -> StartupRouteFlowResult:
        """Record route-flow wiring and return a replacement splash."""

        calls.append("route_flow")
        assert kwargs["entrypoint_path"] == ready_app_launch.entrypoint_path
        assert kwargs["initial_geometry"] == (1, 2, 3, 4)
        assert kwargs["splash"] is initial_splash
        assert kwargs["launch_ready_shell"] is launch_controller.launch
        return StartupRouteFlowResult(
            onboarding_window=onboarding_window,
            route_controller=launch_controller,
            splash=replacement_splash,
            update_splash_reference=True,
        )

    def event_loop(**kwargs: object) -> int:
        """Record event-loop wiring after route dispatch."""

        calls.append("event_loop")
        assert kwargs["app"] is app
        assert kwargs["splash"] is replacement_splash
        assert kwargs["startup_resources"] is startup_resources
        assert kwargs["shutdown_runtime"] is shutdown_runtime
        assert kwargs["shell_reload"] is shell_reload
        assert kwargs["runtime_services"] is runtime_services
        assert kwargs["start_ready_app_process"] is start_ready_app_process
        assert kwargs["keep_alive_references"] == (
            onboarding_window,
            launch_controller,
            shell_frame,
            replacement_splash,
        )
        return 42

    def start_ready_app_process(command: Sequence[str]) -> bool:
        """Record ready-app launch requests."""

        calls.append(f"start:{len(command)}")
        return True

    startup_resources = StartupResourceRegistry()
    monkeypatch.setattr(
        startup_shell_flow,
        "create_startup_ready_shell_launch_graph",
        create_launch_graph,
    )
    monkeypatch.setattr(startup_shell_flow, "run_startup_route_flow", route_flow)
    monkeypatch.setattr(
        startup_shell_flow,
        "run_startup_event_loop_and_shutdown",
        event_loop,
    )

    exit_code = run_startup_shell_flow(
        no_comfy=False,
        handoff_geometry=(1, 2, 3, 4),
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.READY,
            issues=(),
        ),
        installation_context=_installation_context(tmp_path),
        app=app,
        resolved_appearance=resolved_appearance,
        configure_theme=lambda: "theme",
        comfy_output_stream=_OutputStream(),
        runtime_services=runtime_services,
        startup_timer=StartupTimer(clock=_Clock().now),
        startup_resources=startup_resources,
        initial_restore_plan=initial_restore_plan,
        startup_support_graph=support_graph,
        shell_runtime_graph=shell_runtime_graph,
        ready_app_launch=ready_app_launch,
        initial_splash_cancel_connector=None,
        show_onboarding_window=_show_window,
        show_repair_window=_show_window,
        start_ready_app_process=start_ready_app_process,
    )

    assert exit_code == 42
    assert ready_shell_state.reference_state.splash is replacement_splash
    assert calls == [
        "create_launch_graph",
        "connect_cancel",
        "cancel_callback",
        "emit_cancel",
        "route_flow",
        "event_loop",
    ]


def test_startup_shell_flow_imports_no_forbidden_boundaries() -> None:
    """Shell flow should compose bootstrap owners without concrete UI imports."""

    imported_modules = _imported_module_names(SHELL_FLOW_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SHELL_FLOW_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shell_flow() -> None:
    """Startup should delegate route dispatch and event-loop handoff."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_startup_ready_shell_launch_graph(" not in source
    assert "run_startup_route_flow(" not in source
    assert "run_startup_event_loop_and_shutdown(" not in source
    assert "create_startup_ready_shell_launch_graph(" in shell_flow_source
    assert "run_startup_route_flow(" in shell_flow_source
    assert "run_startup_event_loop_and_shutdown(" in shell_flow_source


def _installation_context(tmp_path: Path) -> InstallationContext:
    """Build a minimal installation context for shell-flow tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    return InstallationContext(
        installation=installation,
        runtime=RuntimeConfiguration.create_default(installation),
        comfy_target=ComfyTargetConfiguration.create_default(installation),
    )


def _show_window(**_kwargs: object) -> BootstrapRouteWindowProtocol:
    """Return an inert bootstrap route window."""

    return cast(BootstrapRouteWindowProtocol, object())


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
    """Expose application ports used by shell flow."""

    def exec(self) -> int:
        """Return an inert event-loop result."""

        return 0

    def quit(self) -> None:
        """Accept quit requests."""


class _Splash:
    """Expose launch-splash cleanup behavior."""

    def append_log(self, line: str) -> None:
        """Accept one splash log line."""

        del line

    def close(self) -> None:
        """Accept close requests."""


class _CancelSignal:
    """Record cancel signal wiring."""

    def __init__(self, calls: list[str]) -> None:
        """Store the shared call log."""

        self._calls = calls
        self._callback: Callable[[], None] | None = None

    def connect(self, callback: Callable[[], None]) -> object:
        """Store and invoke the cancel callback."""

        self._calls.append("connect_cancel")
        self._callback = callback
        callback()
        return object()

    def emit(self) -> None:
        """Record cancel signal emission."""

        self._calls.append("emit_cancel")


class _OutputStream:
    """Collect output stream lines."""

    def append_line(self, line: str) -> None:
        """Accept one output line."""

        del line


class _ShellReload:
    """Expose shell reload state consumed by event-loop shutdown."""

    restart_after_cleanup_requested = False
    restart_launch_command = ("python", "main.py")


class _ExecutionRuntime:
    """Expose execution runtime shutdown for shell-flow type checks."""

    def shutdown(self) -> None:
        """Accept shutdown requests."""


class _RuntimeServices:
    """Expose runtime services passed through shell flow."""

    def __init__(self) -> None:
        """Create an inert execution runtime."""

        self.execution_runtime = _ExecutionRuntime()


class _Clock:
    """Return a deterministic monotonic clock value."""

    def now(self) -> float:
        """Return the fixed clock value."""

        return 1.0
