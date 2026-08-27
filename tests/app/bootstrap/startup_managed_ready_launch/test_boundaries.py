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

"""Test managed-ready import-boundary and facade-delegation contracts."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]


STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_launch.py"
)


STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)


STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)


STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"


FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS = frozenset(
    {"substitute.presentation.qt.execution"}
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


def test_managed_ready_launch_imports_no_forbidden_boundaries() -> None:
    """Managed-ready launch assembly should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(STARTUP_MANAGED_READY_LAUNCH_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if imported_module not in ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_managed_ready_shell_launcher_imports_no_forbidden_boundaries() -> None:
    """Managed-ready shell launcher should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(
        STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE
    )
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if imported_module not in ALLOWED_MANAGED_READY_SHELL_LAUNCHER_IMPORTS
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_LAUNCH_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_managed_ready_launch_runtime() -> None:
    """Startup should request one managed-ready launch assembly object."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    ready_launch_source = STARTUP_READY_SHELL_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launcher_source = STARTUP_MANAGED_READY_SHELL_LAUNCHER_SOURCE.read_text(
        encoding="utf-8"
    )

    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_shell_launcher(" not in source
    assert "create_startup_managed_ready_shell_launcher(" in ready_launch_source
    assert "def launch_managed_ready_shell" not in source
    assert "create_startup_managed_ready_launch_runtime(" not in source
    assert "create_startup_managed_ready_state_bundle()" not in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "managed_ready_launch.state" not in source
    assert "managed_ready_launch.runtime" not in source
    assert "create_startup_managed_ready_launch_runtime(" in launch_source
    assert "create_startup_managed_ready_shell_launcher(" not in launch_source
    assert "StartupManagedReadyShellLauncher" not in launch_source
    assert "managed_ready_launch.create_ready_trace_fields(" in launcher_source
    assert (
        "managed_ready_runtime.create_ready_shell_trace_fields_provider("
        not in launcher_source
    )
    assert "managed_ready_launch.create_failure_queue(" in launcher_source
    assert "managed_ready_runtime.create_failure_queue(" not in launcher_source
    assert "managed_ready_launch.create_target_activation_task(" in launcher_source
    assert "managed_ready_runtime.create_target_activation_task(" not in launcher_source
    assert "managed_ready_launch.create_metadata_bridge_task(" in launcher_source
    assert "managed_ready_runtime.create_metadata_bridge_task(" not in launcher_source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launcher_source
    assert (
        "managed_ready_runtime.create_prompt_editor_warmup_task(" not in launcher_source
    )
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launcher_source
    assert (
        "managed_ready_runtime.create_local_editor_warmup_adapter("
        not in launcher_source
    )
    assert "managed_ready_launch.create_managed_startup_prelude(" in launcher_source
    assert (
        "managed_ready_runtime.create_managed_startup_prelude(" not in launcher_source
    )
    assert "managed_ready_launch.create_shell_build_task(" in launcher_source
    assert "managed_ready_runtime.create_shell_build_task(" not in launcher_source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in launcher_source
    )
    assert "managed_ready_launch.create_minimum_ready_task(" in launcher_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in launcher_source
    assert "managed_ready_launch.create_reveal_task(" in launcher_source
    assert "managed_ready_runtime.create_reveal_task(" not in launcher_source
    assert (
        "comfy_http_ready=lambda: ready_state.comfy_http_ready" not in launcher_source
    )
    assert "managed_ready_launch.create_show_gate_task(" in launcher_source
    assert "managed_ready_runtime.create_show_gate_task(" not in launcher_source
    assert "managed_ready_launch.create_post_show_controller(" in launcher_source
    assert "managed_ready_runtime.create_post_show_controller(" not in launcher_source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime("
        not in launcher_source
    )
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter("
        not in launcher_source
    )
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launcher_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller("
        not in launcher_source
    )
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launcher_source
    assert (
        "managed_ready_runtime.bind_startup_readiness_controller("
        not in launcher_source
    )
    assert "managed_ready_launch.schedule_startup_tasks(" in launcher_source
    assert "managed_ready_runtime.schedule_startup_tasks(" not in launcher_source
    assert "start_readiness_timer=readiness_starter.start" not in launcher_source
    assert (
        "backend_state_updater = managed_ready_state.backend_state_updater"
        not in launcher_source
    )
    assert "set_backend_state=backend_state_updater.update" not in launcher_source
    assert "update_backend_state=backend_state_updater.update" not in launcher_source
    assert "backend_state_updater=backend_state_updater" not in launcher_source
