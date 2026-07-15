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

"""Tests for non-ready bootstrap route coordination."""

from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.app.bootstrap.bootstrap_route_controller import (
    BootstrapRouteController,
    BootstrapRouteWindowProtocol,
    create_bootstrap_route_controller,
    trace_bootstrap_route,
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
BOOTSTRAP_ROUTE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "bootstrap_route_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
FORBIDDEN_BOOTSTRAP_ROUTE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
    "substitute.infrastructure",
)


def test_bootstrap_route_controller_shows_onboarding_and_wires_signals(
    tmp_path: Path,
) -> None:
    """Onboarding route should close splash, show onboarding, and wire handoff signals."""

    events: list[str] = []
    controller = _build_controller(events=events)
    context = _build_context(tmp_path)
    assessment = ReadinessAssessment(route=BootstrapRoute.ONBOARDING, issues=())
    onboarding_window = _RouteWindow()
    repair_window = _RouteWindow()
    splash = _Splash(events)

    result = controller.show_onboarding_or_repair_route(
        readiness_assessment=assessment,
        installation_context=context,
        entrypoint_path=tmp_path / "main.py",
        initial_geometry=object(),
        splash=splash,
        show_onboarding_window=lambda **kwargs: _record_window(
            events,
            "onboarding",
            kwargs,
            onboarding_window,
        ),
        show_repair_window=lambda **kwargs: _record_window(
            events,
            "repair",
            kwargs,
            repair_window,
        ),
    )

    assert result.onboarding_window is cast(object, onboarding_window)
    assert result.splash is None
    assert events == ["splash_close", "show_onboarding"]
    assert onboarding_window.launch_requested.callbacks == [
        controller.launch_after_onboarding_completion
    ]
    assert len(onboarding_window.close_requested.callbacks) == 1
    assert repair_window.launch_requested.callbacks == []


def test_bootstrap_route_controller_shows_repair_and_tolerates_splash_close_failure(
    tmp_path: Path,
) -> None:
    """Repair route should continue showing repair when splash close fails."""

    events: list[str] = []
    controller = _build_controller(events=events)
    context = _build_context(tmp_path)
    assessment = ReadinessAssessment(route=BootstrapRoute.REPAIR, issues=())
    repair_window = _RouteWindow()

    result = controller.show_onboarding_or_repair_route(
        readiness_assessment=assessment,
        installation_context=context,
        entrypoint_path=tmp_path / "main.py",
        initial_geometry=None,
        splash=_Splash(events, fail=True),
        show_onboarding_window=lambda **_kwargs: _fail_window("unexpected onboarding"),
        show_repair_window=lambda **kwargs: _record_window(
            events,
            "repair",
            kwargs,
            repair_window,
        ),
    )

    assert result.onboarding_window is cast(object, repair_window)
    assert result.splash is None
    assert events == ["splash_close", "show_repair"]


def test_bootstrap_route_controller_completion_relaunches_ready_app_with_no_comfy(
    tmp_path: Path,
) -> None:
    """Completion launch commands should preserve no-Comfy mode and quit on success."""

    events: list[str] = []
    launched_commands: list[tuple[str, ...]] = []
    context = _build_context(tmp_path)
    controller = _build_controller(
        events=events,
        launched_commands=launched_commands,
        launch_result=True,
    )

    controller.launch_after_onboarding_completion(
        SimpleNamespace(context=context, launch_command=("python", "main.py"))
    )

    assert launched_commands == [("python", "main.py", "--no-comfy")]
    assert events == ["start_process", "quit"]


def test_bootstrap_route_controller_completion_falls_back_to_ready_shell(
    tmp_path: Path,
) -> None:
    """Completion should launch the ready shell when no handoff process starts."""

    events: list[str] = []
    launched_contexts: list[InstallationContext] = []
    context = _build_context(tmp_path)
    controller = _build_controller(
        events=events,
        launched_contexts=launched_contexts,
        launch_result=False,
    )

    controller.launch_after_onboarding_completion(
        SimpleNamespace(context=context, launch_command=("python", "main.py"))
    )
    controller.launch_after_onboarding_completion(context)

    assert events == ["start_process", "launch_ready_shell", "launch_ready_shell"]
    assert launched_contexts == [context, context]


def test_trace_bootstrap_route_emits_prompt_safe_route_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Route tracing should centralize startup route event names and fields."""

    import substitute.app.bootstrap.bootstrap_route_controller as route_controller

    context = _build_context(tmp_path)
    trace_events: list[tuple[str, dict[str, object]]] = []

    def record_trace(event_name: str, **fields: object) -> None:
        """Record one route trace event."""

        trace_events.append((event_name, fields))

    monkeypatch.setattr(route_controller, "trace_mark", record_trace)

    trace_bootstrap_route(
        BootstrapRoute.READY,
        no_comfy=True,
        installation_context=context,
        workspace_present=True,
        shell_placement_present=False,
    )
    trace_bootstrap_route(
        BootstrapRoute.ONBOARDING,
        no_comfy=False,
        installation_context=context,
        workspace_present=False,
        shell_placement_present=True,
    )
    trace_bootstrap_route(
        BootstrapRoute.REPAIR,
        no_comfy=False,
        installation_context=context,
        workspace_present=False,
        shell_placement_present=False,
    )

    assert trace_events == [
        (
            "startup.route.ready",
            {
                "no_comfy": True,
                "target_mode": context.comfy_target.mode,
                "target_host": "127.0.0.1",
                "target_port": 8188,
                "workspace_present": True,
                "shell_placement_present": False,
            },
        ),
        (
            "startup.route.onboarding",
            {
                "no_comfy": False,
                "target_mode": context.comfy_target.mode,
                "target_host": "127.0.0.1",
                "target_port": 8188,
                "workspace_present": False,
                "shell_placement_present": True,
            },
        ),
        (
            "startup.route.repair",
            {
                "no_comfy": False,
                "target_mode": context.comfy_target.mode,
                "target_host": "127.0.0.1",
                "target_port": 8188,
                "workspace_present": False,
                "shell_placement_present": False,
            },
        ),
    ]


def test_create_bootstrap_route_controller_returns_controller(tmp_path: Path) -> None:
    """Bootstrap route factory should construct the concrete route controller."""

    events: list[str] = []

    def start_ready_app_process(_command: Sequence[str]) -> bool:
        """Record launch attempts while forcing direct shell fallback."""

        events.append("start")
        return False

    controller = create_bootstrap_route_controller(
        no_comfy=True,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=lambda _context: events.append("launch"),
        quit_app=lambda: events.append("quit"),
    )

    controller.launch_after_onboarding_completion(_build_context(tmp_path))

    assert isinstance(controller, BootstrapRouteController)
    assert events == ["launch"]


def test_bootstrap_route_controller_imports_no_forbidden_boundaries() -> None:
    """Bootstrap route controller should stay free of Qt and concrete presentation."""

    imported_modules = _imported_module_names(BOOTSTRAP_ROUTE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_BOOTSTRAP_ROUTE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_non_ready_bootstrap_routes() -> None:
    """Startup should no longer own onboarding/repair route implementation."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "run_startup_route_flow(" not in source
    assert "create_bootstrap_route_controller(" not in source
    assert "BootstrapRouteController(" not in source
    assert "def launch_after_onboarding_completion" not in source
    assert "onboarding_window.launch_requested.connect" not in source
    assert "show_window =" not in source
    assert "Failed to close launch splash before routing" not in source
    assert '"startup.route.ready"' not in source
    assert '"startup.route.onboarding"' not in source
    assert '"startup.route.repair"' not in source


def _build_controller(
    *,
    events: list[str],
    launched_commands: list[tuple[str, ...]] | None = None,
    launched_contexts: list[InstallationContext] | None = None,
    launch_result: bool = True,
) -> BootstrapRouteController:
    """Build one controller with recording ports."""

    command_records = launched_commands if launched_commands is not None else []
    context_records = launched_contexts if launched_contexts is not None else []

    def start_ready_app_process(command: Sequence[str]) -> bool:
        """Record one ready-app launch command."""

        events.append("start_process")
        command_records.append(tuple(str(part) for part in command))
        return launch_result

    def launch_ready_shell(context: InstallationContext) -> None:
        """Record one direct ready-shell launch."""

        events.append("launch_ready_shell")
        context_records.append(context)

    return BootstrapRouteController(
        no_comfy=True,
        start_ready_app_process=start_ready_app_process,
        launch_ready_shell=launch_ready_shell,
        quit_app=lambda: events.append("quit"),
    )


def _record_window(
    events: list[str],
    route_name: str,
    kwargs: dict[str, object],
    window: _RouteWindow,
) -> BootstrapRouteWindowProtocol:
    """Record one shown route window and validate expected kwargs."""

    assert "context" in kwargs
    assert "readiness_assessment" in kwargs
    assert "entrypoint_path" in kwargs
    assert "initial_geometry" in kwargs
    events.append(f"show_{route_name}")
    return window


def _build_context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic installation context for route tests."""

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
    """Fail a callback that should not be invoked."""

    raise AssertionError(message)


class _Signal:
    """Record connected callbacks."""

    def __init__(self) -> None:
        """Initialize callback storage."""

        self.callbacks: list[object] = []

    def connect(self, callback: Callable[..., object]) -> None:
        """Record one connected callback."""

        self.callbacks.append(callback)


class _RouteWindow:
    """Provide route window signals for controller tests."""

    def __init__(self) -> None:
        """Initialize fake route-window signals."""

        self.launch_requested = _Signal()
        self.close_requested = _Signal()


class _Splash:
    """Record splash close attempts."""

    def __init__(self, events: list[str], *, fail: bool = False) -> None:
        """Store close behavior for one fake splash."""

        self._events = events
        self._fail = fail

    def close(self) -> None:
        """Record splash close and optionally fail."""

        self._events.append("splash_close")
        if self._fail:
            raise RuntimeError("close failed")
