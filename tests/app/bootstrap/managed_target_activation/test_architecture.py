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

"""Qualify managed-target activation dependency boundaries."""

from __future__ import annotations

from pathlib import Path


from tests.app.bootstrap.managed_target_activation.support import (
    imported_module_names as _imported_module_names,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ACTIVATION_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "managed_target_activation.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_ACTIVATION_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "subprocess",
)


def test_managed_target_activation_imports_no_forbidden_boundaries() -> None:
    """Managed activation should stay free of Qt, presentation, and subprocess."""

    imported_modules = _imported_module_names(ACTIVATION_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_ACTIVATION_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_no_longer_owns_managed_target_activation() -> None:
    """Startup should delegate managed target activation helpers."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    managed_ready_runtime_source = (
        PROJECT_ROOT
        / "substitute"
        / "app"
        / "bootstrap"
        / "startup_managed_ready_runtime.py"
    ).read_text(encoding="utf-8")

    assert "def _activate_target" not in source
    assert "def _collect_and_fan_out_comfy_output" not in source
    assert "def _fan_out_splash_and_shell_output" not in source
    assert "def _managed_startup_fatal_incident" not in source
    assert "TerminalOutputStream" not in ACTIVATION_SOURCE.read_text(encoding="utf-8")
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task(" not in source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "managed_ready_runtime.activate_target" not in source
    assert "fan_out_splash_and_shell_output(" not in source
    assert "managed_startup_fatal_incident(" not in source
    assert "managed_startup_fatal_incident(" in managed_ready_runtime_source
