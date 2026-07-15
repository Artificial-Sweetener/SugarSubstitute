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

"""Tests for startup-facing route flow dispatch."""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
import gc
from pathlib import Path
from typing import cast
import weakref

import pytest
from PySide6.QtCore import QObject, Signal

from substitute.app.bootstrap import startup_route_flow
from substitute.app.bootstrap.bootstrap_route_controller import (
    BootstrapRouteWindowProtocol,
)
from substitute.domain.onboarding import (
    BootstrapRoute,
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    ReadinessAssessment,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_ROUTE_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_route_flow.py"
)
FORBIDDEN_STARTUP_ROUTE_FLOW_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "substitute.infrastructure",
)


def test_route_flow_traces_and_launches_ready_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ready route should trace prompt-safe fields and launch the ready shell."""

    events: list[tuple[str, object]] = []
    context = _build_context(tmp_path)
    workspace = object()
    shell_placement = object()
    splash = _Splash(events)

    def trace_route(route: BootstrapRoute, **fields: object) -> None:
        """Record the route trace call."""

        events.append(("trace", route))
        events.append(("trace_fields", fields))

    monkeypatch.setattr(startup_route_flow, "trace_bootstrap_route", trace_route)

    result = startup_route_flow.run_startup_route_flow(
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.READY,
            issues=(),
        ),
        no_comfy=True,
        installation_context=context,
        initial_workspace=workspace,
        initial_shell_placement=shell_placement,
        entrypoint_path=tmp_path / "main.py",
        initial_geometry=None,
        splash=splash,
        show_onboarding_window=lambda **_kwargs: _fail_window("onboarding"),
        show_repair_window=lambda **_kwargs: _fail_window("repair"),
        start_ready_app_process=lambda _command: _fail_bool("process"),
        launch_ready_shell=lambda launch_context: events.append(
            ("launch", launch_context)
        ),
        quit_app=lambda: events.append(("quit", None)),
    )

    assert result.onboarding_window is None
    assert result.route_controller is None
    assert result.splash is splash
    assert result.update_splash_reference is False
    assert events == [
        ("trace", BootstrapRoute.READY),
        (
            "trace_fields",
            {
                "no_comfy": True,
                "installation_context": context,
                "workspace_present": True,
                "shell_placement_present": True,
            },
        ),
        ("launch", context),
    ]


def test_route_flow_shows_non_ready_route_and_returns_live_references(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-ready route should delegate window construction to the route controller."""

    events: list[tuple[str, object]] = []
    context = _build_context(tmp_path)
    assessment = ReadinessAssessment(route=BootstrapRoute.REPAIR, issues=())
    repair_window = _RouteWindow()
    splash = _Splash(events)

    def trace_route(route: BootstrapRoute, **fields: object) -> None:
        """Record the route trace call."""

        events.append(("trace", route))
        events.append(("trace_fields", fields))

    def show_repair_window(**kwargs: object) -> BootstrapRouteWindowProtocol:
        """Record repair window construction."""

        events.append(("show_repair", kwargs))
        return repair_window

    monkeypatch.setattr(startup_route_flow, "trace_bootstrap_route", trace_route)

    result = startup_route_flow.run_startup_route_flow(
        readiness_assessment=assessment,
        no_comfy=False,
        installation_context=context,
        initial_workspace=None,
        initial_shell_placement=None,
        entrypoint_path=tmp_path / "main.py",
        initial_geometry="geometry",
        splash=splash,
        show_onboarding_window=lambda **_kwargs: _fail_window("onboarding"),
        show_repair_window=show_repair_window,
        start_ready_app_process=lambda _command: False,
        launch_ready_shell=lambda launch_context: events.append(
            ("launch", launch_context)
        ),
        quit_app=lambda: events.append(("quit", None)),
    )

    assert result.onboarding_window is repair_window
    assert result.route_controller is not None
    assert result.splash is None
    assert result.update_splash_reference is True
    assert events == [
        ("trace", BootstrapRoute.REPAIR),
        (
            "trace_fields",
            {
                "no_comfy": False,
                "installation_context": context,
                "workspace_present": False,
                "shell_placement_present": False,
            },
        ),
        ("splash_close", splash),
        (
            "show_repair",
            {
                "context": context,
                "readiness_assessment": assessment,
                "entrypoint_path": tmp_path / "main.py",
                "initial_geometry": "geometry",
            },
        ),
    ]
    assert repair_window.launch_requested.callbacks
    assert repair_window.close_requested.callbacks


def test_non_ready_route_retains_controller_for_qt_signal_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Route ownership should keep weak Qt signal callbacks alive until handoff."""

    context = _build_context(tmp_path)
    route_window = _QtRouteWindow()
    launched_commands: list[tuple[str, ...]] = []
    quit_requests: list[bool] = []
    monkeypatch.setattr(
        startup_route_flow, "trace_bootstrap_route", lambda *_args, **_kwargs: None
    )

    def show_onboarding_window(**_kwargs: object) -> BootstrapRouteWindowProtocol:
        """Return the real Qt signal surface through the route protocol."""

        return cast(BootstrapRouteWindowProtocol, route_window)

    def start_ready_app_process(command: Sequence[str]) -> bool:
        """Record one successful ready-app handoff."""

        launched_commands.append(tuple(command))
        return True

    result = startup_route_flow.run_startup_route_flow(
        readiness_assessment=ReadinessAssessment(
            route=BootstrapRoute.ONBOARDING,
            issues=(),
        ),
        no_comfy=False,
        installation_context=context,
        initial_workspace=None,
        initial_shell_placement=None,
        entrypoint_path=tmp_path / "main.py",
        initial_geometry=None,
        splash=None,
        show_onboarding_window=show_onboarding_window,
        show_repair_window=lambda **_kwargs: _fail_window("repair"),
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=lambda _context: _fail_none("ready shell"),
        quit_app=lambda: quit_requests.append(True),
    )
    controller_reference = weakref.ref(result.route_controller)

    gc.collect()
    route_window.launch_requested.emit(
        _Completion(context=context, launch_command=("python", "main.py"))
    )

    assert controller_reference() is result.route_controller
    assert launched_commands == [("python", "main.py")]
    assert quit_requests == [True]


def test_startup_route_flow_imports_no_forbidden_boundaries() -> None:
    """Route flow should stay free of Qt, presentation, and process execution."""

    imported_modules = _imported_module_names(STARTUP_ROUTE_FLOW_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_STARTUP_ROUTE_FLOW_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_route_flow() -> None:
    """Startup should request route-flow dispatch instead of owning route branching."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "run_startup_route_flow(" not in source
    assert "run_startup_route_flow(" in shell_flow_source
    assert "BootstrapRoute" not in source
    assert "readiness_assessment.route is" not in source
    assert "create_bootstrap_route_controller(" not in source
    assert "trace_bootstrap_route(" not in source
    assert "show_onboarding_or_repair_route(" not in source


def _build_context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic installation context for route-flow tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


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


def _fail_window(message: str) -> BootstrapRouteWindowProtocol:
    """Fail a window callback that should not be invoked."""

    raise AssertionError(message)


def _fail_bool(message: str) -> bool:
    """Fail a boolean callback that should not be invoked."""

    raise AssertionError(message)


def _fail_none(message: str) -> None:
    """Fail a callback that should not be invoked."""

    raise AssertionError(message)


class _Completion:
    """Provide the completion fields consumed by the bootstrap route."""

    def __init__(
        self,
        *,
        context: InstallationContext,
        launch_command: tuple[str, ...],
    ) -> None:
        """Store one deterministic launch handoff."""

        self.context = context
        self.launch_command = launch_command


class _QtRouteWindow(QObject):
    """Expose real Qt signals whose bound-method connections are weak."""

    launch_requested = Signal(object)
    close_requested = Signal()


class _Signal:
    """Record connected route callbacks."""

    def __init__(self) -> None:
        """Initialize callback storage."""

        self.callbacks: list[Callable[..., object]] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)


class _RouteWindow:
    """Provide route window signals for route-flow tests."""

    def __init__(self) -> None:
        """Initialize fake signals."""

        self.launch_requested = _Signal()
        self.close_requested = _Signal()


class _Splash:
    """Record splash close attempts."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        """Store event sink."""

        self._events = events

    def close(self) -> None:
        """Record one close call."""

        self._events.append(("splash_close", self))
