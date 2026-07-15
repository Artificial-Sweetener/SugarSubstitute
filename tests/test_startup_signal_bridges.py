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

"""Tests for Qt startup signal bridge adapters."""

from __future__ import annotations

import ast
from pathlib import Path

from substitute.app.bootstrap.startup_signal_bridges import (
    ManagedCompatibilityRecoveryBridge,
    StartupDiagnosticsTitlebarBridge,
    connect_managed_compatibility_recovery_bridge,
    create_managed_compatibility_recovery_bridge,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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
STARTUP_SIGNAL_BRIDGES_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_signal_bridges.py"
)
FORBIDDEN_SIGNAL_BRIDGE_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_startup_diagnostics_titlebar_bridge_emits_prepared_state() -> None:
    """Diagnostics bridge should publish prepared titlebar state objects."""

    bridge = StartupDiagnosticsTitlebarBridge()
    states: list[object] = []
    state = object()

    bridge.prepared.connect(states.append)
    bridge.prepared.emit(state)

    assert states == [state]


def test_managed_compatibility_recovery_bridge_emits_finished_state() -> None:
    """Managed recovery bridge should publish finished recovery objects."""

    bridge = ManagedCompatibilityRecoveryBridge()
    states: list[object] = []
    state = object()

    bridge.finished.connect(states.append)
    bridge.finished.emit(state)

    assert states == [state]


def test_create_managed_compatibility_recovery_bridge_returns_signal_bridge() -> None:
    """Managed recovery bridge factory should provide the Qt signal adapter."""

    bridge = create_managed_compatibility_recovery_bridge()
    states: list[object] = []
    state = object()

    bridge.finished.connect(states.append)
    bridge.finished.emit(state)

    assert states == [state]


def test_connect_managed_compatibility_recovery_bridge_wires_completion() -> None:
    """Managed recovery bridge connector should own finished-signal wiring."""

    bridge = create_managed_compatibility_recovery_bridge()
    states: list[object] = []
    state = object()

    connect_managed_compatibility_recovery_bridge(
        bridge=bridge,
        callback=states.append,
    )
    bridge.finished.emit(state)

    assert states == [state]


def test_startup_signal_bridges_import_no_forbidden_boundaries() -> None:
    """Startup signal bridges should stay focused on Qt signal delivery."""

    imported_modules = _imported_module_names(STARTUP_SIGNAL_BRIDGES_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_SIGNAL_BRIDGE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_startup_signal_bridges() -> None:
    """Startup should use bridge factories instead of defining or constructing bridges."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = MANAGED_READY_RUNTIME_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "class _StartupDiagnosticsTitlebarBridge" not in source
    assert "class _ManagedCompatibilityRecoveryBridge" not in source
    assert "StartupDiagnosticsTitlebarBridge()" not in source
    assert "ManagedCompatibilityRecoveryBridge()" not in source
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "create_managed_compatibility_recovery_bridge()" not in source
    assert "managed_compatibility_recovery_bridge.finished.connect(" not in source
    assert "connect_managed_compatibility_recovery_bridge(" not in source
    assert (
        "managed_ready_runtime.publish_managed_compatibility_recovery_outcome"
        not in source
    )
    assert (
        "managed_ready_runtime.connect_managed_compatibility_recovery_finished"
        not in source
    )
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in source
    )
    assert (
        "create_managed_compatibility_recovery_bridge()" in managed_ready_runtime_source
    )
    assert (
        "connect_managed_compatibility_recovery_bridge(" in managed_ready_runtime_source
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
