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

"""Test managed-ready runtime dependency boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MANAGED_READY_RUNTIME_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_runtime.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
FORBIDDEN_MANAGED_READY_RUNTIME_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_managed_ready_runtime_imports_no_forbidden_boundaries() -> None:
    """Managed-ready runtime composition should stay outside UI and infrastructure."""

    imported_modules = _imported_module_names(MANAGED_READY_RUNTIME_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_MANAGED_READY_RUNTIME_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_uses_managed_ready_runtime_resources() -> None:
    """Startup should delegate managed-ready runtime resource setup."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")
    assert "run_startup_shell_flow(" in source
    assert "create_startup_managed_ready_runtime_resources(" not in source
    assert "managed_ready_runtime.startup_diagnostics" not in source
    assert "managed_ready_runtime.startup_ignore_repository" not in source
    assert "managed_ready_runtime.readiness_runtime_adapters" not in source
    assert "managed_ready_runtime.managed_failure_report_adapter" not in source
    assert "managed_ready_runtime.present_startup_failure_report" not in source
    assert "managed_ready_launch.create_failure_queue" in launch_source
    assert "managed_ready_runtime.create_failure_queue" not in source
    assert "managed_ready_launch.create_shell_build_task(" in launch_source
    assert "managed_ready_runtime.create_shell_build_task" not in source
    assert "managed_ready_runtime.managed_startup_compatibility_assessor" not in source
    assert "managed_ready_runtime.activate_target" not in source
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task" not in source
    assert "managed_ready_runtime.managed_startup_fatal_incident" not in source
    assert "managed_ready_runtime.create_model_metadata_update_bridge" not in source
    assert "managed_ready_launch.create_metadata_bridge_task" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task" not in source
    assert "managed_ready_launch.create_ready_trace_fields(" in launch_source
    assert (
        "managed_ready_runtime.create_ready_shell_trace_fields_provider" not in source
    )
    assert "managed_ready_runtime.start_local_editor_startup_warmup" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert "managed_ready_runtime.create_local_editor_warmup_adapter" not in source
    assert "managed_ready_runtime.start_cutecanvas_sam_startup_warmup" not in source
    assert (
        "managed_ready_launch.create_cutecanvas_sam_warmup_callback(" in launch_source
    )
    assert "start_cutecanvas_sam_warmup()" in launch_source
    assert "prerequisite_ready=cutecanvas_sam_warmup_is_terminal" in launch_source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller" not in source
    assert (
        "managed_ready_launch.create_nonessential_startup_warmup_runtime"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_nonessential_startup_warmup_runtime" not in source
    )
    assert "managed_ready_runtime.restored_active_workflow_id" not in source
    assert "managed_ready_runtime.restored_workspace_workflow_count" not in source
    assert "managed_ready_runtime.warm_prompt_editor_gui_from_window" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task" in launch_source
    assert "managed_ready_runtime.create_prompt_editor_warmup_task" not in source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task" not in source
    )
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task" not in source
    assert "managed_ready_launch.create_reveal_task(" in launch_source
    assert "managed_ready_runtime.create_reveal_task" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task" not in source
    assert "managed_ready_launch.schedule_startup_tasks" in launch_source
    assert "managed_ready_runtime.schedule_startup_tasks" not in source
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter" not in source
    )
    assert "managed_ready_runtime.create_readiness_failure_adapter" not in source
    assert "managed_ready_launch.bind_startup_readiness_controller(" in launch_source
    assert "managed_ready_runtime.bind_startup_readiness_controller" not in source
    assert (
        "managed_ready_launch.create_managed_compatibility_recovery_controller("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_managed_compatibility_recovery_controller"
        not in source
    )
    assert (
        "managed_ready_runtime.create_managed_recovery_startup_adapters" not in source
    )
    assert "startup_adapters=" not in source
    assert "managed_ready_runtime.managed_recovery_controller_adapters" not in source
    assert (
        "managed_ready_runtime.publish_managed_compatibility_recovery_outcome"
        not in source
    )
    assert (
        "managed_ready_runtime.connect_managed_compatibility_recovery_finished"
        not in source
    )
    assert "start_local_editor_warmup=start_local_editor_startup_warmup" not in source
    assert (
        "start_cutecanvas_sam_warmup=start_cutecanvas_sam_startup_warmup" not in source
    )
    assert "fallback_workflow_id=lambda: restored_active_workflow_id" not in source
    assert "workspace_workflow_count=restored_workspace_workflow_count" not in source
    assert (
        "from substitute.app.bootstrap.startup_restore_workspace import" not in source
    )
    assert "managed_ready_runtime.managed_compatibility_checker" not in source
    assert "managed_ready_runtime.managed_compatibility_recovery_bridge" not in source
    assert "managed_ready_ports.create_startup_diagnostics_collector()" not in source
    assert "managed_ready_ports.activate_target" not in source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "create_ready_shell_build_task(" not in source
    assert "managed_ready_ports.managed_startup_fatal_incident" not in source
    assert "managed_ready_ports.present_startup_failure_report" not in source
    assert "create_ready_shell_failure_queue(" not in source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "managed_ready_ports.create_model_metadata_update_bridge" not in source
    assert "create_ready_shell_metadata_bridge_task(" not in source
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "create_ready_shell_reveal_task(" not in source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "schedule_ready_shell_controller_startup_tasks(" not in source
    assert "create_startup_managed_failure_report_adapter(" not in source
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "create_startup_readiness_failure_adapter(" not in source
    assert "create_bound_startup_readiness_controller(" not in source
    assert "from substitute.app.bootstrap.ready_shell_trace_fields import" not in source
    assert "from substitute.app.bootstrap.prompt_editor_gui_warmup import" not in source
    assert (
        "from substitute.app.bootstrap.startup_warmup_controller import" not in source
    )
    assert (
        "from substitute.app.bootstrap.managed_recovery_adapters import" not in source
    )
    assert "connect_managed_compatibility_recovery_bridge(" not in source
    assert (
        "managed_ready_ports.create_startup_diagnostics_ignore_repository(context)"
        not in source
    )
    assert "StartupReadinessRuntimeAdapters(" not in source
    assert "managed_ready_ports.create_runtime_compatibility_checker()" not in source
    assert (
        "managed_ready_ports.create_managed_compatibility_recovery_bridge()"
        not in source
    )
    assert "create_connected_managed_compatibility_recovery_controller(" not in source
    assert (
        "from substitute.app.bootstrap.managed_compatibility_recovery import"
        not in source
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
