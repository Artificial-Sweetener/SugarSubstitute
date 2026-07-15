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

"""Tests for startup support graph composition."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from typing import TypeVar, cast

import pytest

from substitute.app.bootstrap import startup_support_graph
from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.ready_shell_state import ReadyShellStateBundle
from substitute.app.bootstrap.shell_reload_adapter import StartupShellReloadState
from substitute.app.bootstrap.startup_cancellation import StartupCancellationState
from substitute.app.bootstrap.startup_ports import (
    StartupManagedReadyFactoryPorts,
    StartupShellCompositionPorts,
)
from substitute.app.bootstrap.startup_qt_timers import StartupQtSchedulerPorts
from substitute.app.bootstrap.startup_splash_controller import (
    StartupCancelBridge,
    StartupSplashPorts,
)
from substitute.app.bootstrap.startup_support_graph import (
    StartupSupportGraph,
    create_startup_support_graph,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
FORBIDDEN_SUPPORT_GRAPH_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "subprocess",
    "substitute.infrastructure",
    "substitute.presentation",
)
_T = TypeVar("_T")


def test_create_startup_support_graph_groups_support_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Support graph factory should compose the startup support object graph."""

    calls: list[str] = []
    initial_splash = cast(LaunchSplashClient, object())
    ready_shell_state = cast(ReadyShellStateBundle, object())
    shell_reload_state = cast(StartupShellReloadState, object())
    startup_cancel_bridge = cast(StartupCancelBridge, object())
    startup_cancellation_state = cast(StartupCancellationState, object())
    startup_qt_schedulers = cast(StartupQtSchedulerPorts, object())
    shell_ports = cast(StartupShellCompositionPorts, object())
    managed_ready_ports = cast(StartupManagedReadyFactoryPorts, object())

    def create_ready_shell_state_bundle(
        *,
        initial_splash: LaunchSplashClient | None = None,
    ) -> ReadyShellStateBundle:
        """Record ready-shell state construction."""

        calls.append("ready_shell_state")
        assert initial_splash is initial_splash_value
        return ready_shell_state

    def create_startup_splash_ports() -> StartupSplashPorts:
        """Record splash port construction."""

        calls.append("splash_ports")
        return StartupSplashPorts(
            create_cancel_bridge=create_startup_cancel_bridge,
            start_or_adopt_launch_splash=lambda **_kwargs: initial_splash,
        )

    def create_startup_cancel_bridge() -> StartupCancelBridge:
        """Record cancel bridge construction."""

        calls.append("cancel_bridge")
        return startup_cancel_bridge

    initial_splash_value = initial_splash
    monkeypatch.setattr(
        startup_support_graph,
        "create_ready_shell_state_bundle",
        create_ready_shell_state_bundle,
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_shell_reload_state",
        lambda: _record(calls, "shell_reload_state", shell_reload_state),
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_splash_ports",
        create_startup_splash_ports,
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_cancellation_state",
        lambda: _record(calls, "cancellation_state", startup_cancellation_state),
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_qt_scheduler_ports",
        lambda: _record(calls, "qt_schedulers", startup_qt_schedulers),
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_shell_composition_ports",
        lambda: _record(calls, "shell_ports", shell_ports),
    )
    monkeypatch.setattr(
        startup_support_graph,
        "create_startup_managed_ready_factory_ports",
        lambda: _record(calls, "managed_ready_ports", managed_ready_ports),
    )

    graph = create_startup_support_graph(initial_splash=initial_splash)

    assert isinstance(graph, StartupSupportGraph)
    assert graph.ready_shell_state is ready_shell_state
    assert graph.shell_reload_state is shell_reload_state
    assert graph.startup_cancel_bridge is startup_cancel_bridge
    assert graph.startup_cancellation_state is startup_cancellation_state
    assert graph.startup_qt_schedulers is startup_qt_schedulers
    assert graph.shell_ports is shell_ports
    assert graph.managed_ready_ports is managed_ready_ports
    assert calls == [
        "splash_ports",
        "ready_shell_state",
        "shell_reload_state",
        "cancel_bridge",
        "cancellation_state",
        "qt_schedulers",
        "shell_ports",
        "managed_ready_ports",
    ]
    assert [field.name for field in fields(graph)] == [
        "ready_shell_state",
        "shell_reload_state",
        "startup_splash_ports",
        "startup_cancel_bridge",
        "startup_cancellation_state",
        "startup_qt_schedulers",
        "shell_ports",
        "managed_ready_ports",
    ]


def test_startup_support_graph_imports_no_forbidden_boundaries() -> None:
    """Support graph should compose bootstrap adapters without concrete UI imports."""

    imported_modules = _imported_module_names(SUPPORT_GRAPH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SUPPORT_GRAPH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_startup_support_graph() -> None:
    """Startup should request support graph composition through one owner."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")

    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_ready_shell_state_bundle(" not in source
    assert "create_startup_shell_reload_state()" not in source
    assert "create_startup_splash_ports()" not in source
    assert "startup_splash_ports.create_cancel_bridge()" not in source
    assert "create_startup_cancellation_state()" not in source
    assert "create_startup_qt_scheduler_ports()" not in source
    assert "create_startup_shell_composition_ports()" not in source
    assert "create_startup_managed_ready_factory_ports()" not in source
    assert "create_ready_shell_state_bundle(" in support_graph_source
    assert "create_startup_shell_reload_state()" in support_graph_source
    assert "create_startup_splash_ports()" in support_graph_source
    assert "startup_splash_ports.create_cancel_bridge()" in support_graph_source
    assert "create_startup_cancellation_state()" in support_graph_source
    assert "create_startup_qt_scheduler_ports()" in support_graph_source
    assert "create_startup_shell_composition_ports()" in support_graph_source
    assert "create_startup_managed_ready_factory_ports()" in support_graph_source


def _record(calls: list[str], name: str, value: _T) -> _T:
    """Record one factory call and return its fake value."""

    calls.append(name)
    return value


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
