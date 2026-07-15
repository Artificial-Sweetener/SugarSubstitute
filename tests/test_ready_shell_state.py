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

"""Tests for ready-shell startup state."""

from __future__ import annotations

import ast
from dataclasses import fields
from pathlib import Path
from typing import cast

from substitute.app.bootstrap.launch_splash import LaunchSplashClient
from substitute.app.bootstrap.startup_model_metadata import (
    ModelMetadataUpdateSignalBridgeProtocol,
)
from substitute.app.bootstrap.ready_shell_state import (
    ReadyShellReferenceState,
    ReadyShellRuntimeState,
    ReadyShellStateBundle,
    ReadyShellStartupState,
    create_ready_shell_state_bundle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
READY_STATE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_state.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SUPPORT_GRAPH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_support_graph.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_READY_STATE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_startup_state_defaults_to_all_gates_closed() -> None:
    """Ready-shell startup gates should start closed."""

    state = ReadyShellStartupState()

    assert state.comfy_activation_started is False
    assert state.minimum_shell_ready is False
    assert state.comfy_http_ready is False
    assert state.main_window_shown is False
    assert state.prehydration_attempted is False
    assert state.prehydration_succeeded is False
    assert state.hydration_started is False
    assert [field.name for field in fields(state)] == [
        "comfy_activation_started",
        "minimum_shell_ready",
        "comfy_http_ready",
        "main_window_shown",
        "prehydration_attempted",
        "prehydration_succeeded",
        "hydration_started",
    ]


def test_ready_shell_runtime_state_tracks_runtime_references() -> None:
    """Ready-shell runtime state should own mutable startup references."""

    state = ReadyShellRuntimeState()
    comfy_state = object()
    metadata_bridge = cast(ModelMetadataUpdateSignalBridgeProtocol, object())

    state.set_comfy_state(comfy_state)
    state.set_metadata_update_bridge(metadata_bridge)

    assert state.comfy_state is comfy_state
    assert state.metadata_update_bridge is metadata_bridge
    assert [field.name for field in fields(state)] == [
        "comfy_state",
        "metadata_update_bridge",
    ]


def test_ready_shell_reference_state_tracks_live_startup_references() -> None:
    """Ready-shell reference state should own mutable startup references."""

    state = ReadyShellReferenceState()
    splash = cast(LaunchSplashClient, object())

    state.set_splash(splash)
    state.set_hidden_restore_runtime_prepared(True)

    assert state.splash is splash
    assert state.hidden_restore_runtime_prepared is True
    assert [field.name for field in fields(state)] == [
        "splash",
        "hidden_restore_runtime_prepared",
    ]


def test_ready_shell_state_bundle_creates_reference_and_runtime_state() -> None:
    """Ready-shell state factory should own startup state object composition."""

    splash = cast(LaunchSplashClient, object())

    bundle = create_ready_shell_state_bundle(initial_splash=splash)

    assert isinstance(bundle, ReadyShellStateBundle)
    assert isinstance(bundle.reference_state, ReadyShellReferenceState)
    assert isinstance(bundle.runtime_state, ReadyShellRuntimeState)
    assert bundle.reference_state.splash is splash
    assert bundle.reference_state.hidden_restore_runtime_prepared is False
    assert bundle.runtime_state.comfy_state is None
    assert bundle.runtime_state.metadata_update_bridge is None
    assert [field.name for field in fields(bundle)] == [
        "reference_state",
        "runtime_state",
    ]


def test_ready_shell_state_imports_no_forbidden_boundaries() -> None:
    """Ready-shell state should stay free of Qt, presentation, and infrastructure."""

    imported_modules = _imported_module_names(READY_STATE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_STATE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_ready_shell_state() -> None:
    """Startup should delegate ready-shell state shape to the extracted owner."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    assert "class _ReadyShellStartupState" not in source
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_state_bundle()" not in source
    assert "ReadyShellStartupState()" not in source


def test_startup_facade_uses_ready_shell_runtime_state() -> None:
    """Startup should not keep local ready-shell runtime reference setters."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")
    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_ready_shell_state_bundle(" not in source
    assert "create_ready_shell_state_bundle(" in support_graph_source
    assert "ReadyShellRuntimeState()" not in source
    assert "def set_ready_shell_comfy_state" not in source
    assert "def set_metadata_update_bridge_reference" not in source
    assert "def current_managed_comfy_state" not in source
    assert "def set_managed_comfy_state" not in source


def test_startup_facade_uses_ready_shell_reference_state() -> None:
    """Startup should not keep local splash or hidden-runtime setters."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    support_graph_source = SUPPORT_GRAPH_SOURCE.read_text(encoding="utf-8")
    assert "create_startup_support_graph(initial_splash=initial_splash)" in source
    assert "create_ready_shell_state_bundle(" not in source
    assert "create_ready_shell_state_bundle(" in support_graph_source
    assert "ReadyShellReferenceState(" not in source
    assert "def set_splash" not in source
    assert "def set_hidden_restore_runtime_prepared" not in source
    assert "nonlocal splash" not in source
    assert "hidden_restore_runtime_prepared = False" not in source


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
