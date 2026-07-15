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

"""Tests for managed-ready startup state composition."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.app.bootstrap.managed_compatibility_recovery import (
    ManagedCompatibilityRecoveryControllerState,
)
from substitute.app.bootstrap.pre_show_restore_projection import (
    PreShowRestoreProjectionState,
)
from substitute.app.bootstrap.ready_shell_controller import (
    ReadyShellBackendStateUpdater,
)
from substitute.app.bootstrap.ready_shell_state import ReadyShellStartupState
from substitute.app.bootstrap.startup_managed_ready_state import (
    create_startup_managed_ready_state_bundle,
)
from substitute.app.bootstrap.startup_model_metadata import (
    StartupModelMetadataRefreshState,
)
from substitute.app.bootstrap.startup_readiness_controller import (
    StartupReadinessControllerState,
    StartupReadinessStarter,
)
from substitute.app.bootstrap.startup_warmup_controller import StartupWarmupState

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGED_READY_STATE_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_managed_ready_state.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_MANAGED_READY_STATE_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_managed_ready_state_bundle_creates_controller_state_defaults() -> None:
    """Managed-ready state composition should create each controller state owner."""

    bundle = create_startup_managed_ready_state_bundle()

    assert isinstance(bundle.ready_state, ReadyShellStartupState)
    assert isinstance(
        bundle.model_metadata_refresh_state,
        StartupModelMetadataRefreshState,
    )
    assert isinstance(bundle.startup_warmup_state, StartupWarmupState)
    assert isinstance(
        bundle.readiness_controller_state,
        StartupReadinessControllerState,
    )
    assert isinstance(bundle.readiness_starter, StartupReadinessStarter)
    assert isinstance(bundle.backend_state_updater, ReadyShellBackendStateUpdater)
    assert isinstance(
        bundle.managed_compatibility_recovery_state,
        ManagedCompatibilityRecoveryControllerState,
    )
    assert isinstance(
        bundle.pre_show_restore_projection_state,
        PreShowRestoreProjectionState,
    )

    assert bundle.ready_state.comfy_activation_started is False
    assert bundle.model_metadata_refresh_state.started is False
    assert bundle.startup_warmup_state.local_editor_started is False
    assert bundle.readiness_controller_state.readiness_attempts == 0
    assert bundle.managed_compatibility_recovery_state.recovery_attempted is False
    assert bundle.pre_show_restore_projection_state.pending is False
    with pytest.raises(RuntimeError, match="not bound"):
        bundle.readiness_starter.start()


def test_managed_ready_state_imports_no_forbidden_boundaries() -> None:
    """Managed-ready state composition should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(MANAGED_READY_STATE_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_STATE_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_managed_ready_state_bundle() -> None:
    """Startup should not directly construct managed-ready controller state."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_state_bundle()" not in source
    assert "ReadyShellStartupState()" not in source
    assert "StartupModelMetadataRefreshState()" not in source
    assert "StartupWarmupState()" not in source
    assert "StartupReadinessControllerState()" not in source
    assert "StartupReadinessStarter()" not in source
    assert "ReadyShellBackendStateUpdater()" not in source
    assert "ManagedCompatibilityRecoveryControllerState()" not in source
    assert "PreShowRestoreProjectionState()" not in source
    assert "managed_ready_state.pre_show_restore_projection_state" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source


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
