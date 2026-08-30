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

"""Tests for ready-shell startup task orchestration."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
READY_SHELL_CONTROLLER_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "ready_shell_controller.py"
)
STARTUP_SOURCE = PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup.py"
SHELL_FLOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_shell_flow.py"
)
STARTUP_MANAGED_READY_LAUNCH_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "app"
    / "bootstrap"
    / "startup_managed_ready_shell_launcher.py"
)
STARTUP_READY_SHELL_LAUNCH_SOURCE = (
    PROJECT_ROOT / "substitute" / "app" / "bootstrap" / "startup_ready_shell_launch.py"
)
FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES = (
    "PySide6",
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation",
    "substitute.infrastructure",
    "subprocess",
)


def test_ready_shell_controller_imports_no_forbidden_boundaries() -> None:
    """Ready-shell orchestration should stay behind explicit startup ports."""

    imported_modules = _imported_module_names(READY_SHELL_CONTROLLER_SOURCE)
    forbidden_imports = tuple(
        imported_module
        for imported_module in sorted(imported_modules)
        if any(
            imported_module == prefix or imported_module.startswith(f"{prefix}.")
            for prefix in FORBIDDEN_READY_SHELL_CONTROLLER_IMPORT_PREFIXES
        )
    )

    assert forbidden_imports == ()


def test_startup_facade_delegates_shell_build_task() -> None:
    """Startup should delegate shell-build task internals to ready-shell owner."""

    source = STARTUP_SOURCE.read_text(encoding="utf-8")
    shell_flow_source = SHELL_FLOW_SOURCE.read_text(encoding="utf-8")
    ready_launch_source = STARTUP_READY_SHELL_LAUNCH_SOURCE.read_text(encoding="utf-8")
    launch_source = STARTUP_MANAGED_READY_LAUNCH_SOURCE.read_text(encoding="utf-8")

    assert "run_startup_shell_flow(" in source
    assert "create_startup_ready_shell_launch_controller(" not in source
    assert "create_startup_managed_ready_shell_launcher(" not in source
    assert "create_startup_managed_ready_shell_launcher(" in ready_launch_source
    assert (
        "launch_managed_ready_shell=managed_ready_shell_launcher.launch"
        in ready_launch_source
    )
    assert "create_ready_shell_launch_controller(" not in source
    assert "ReadyShellLaunchController(" not in source
    assert "managed_ready_launch.create_failure_queue(" in launch_source
    assert "managed_ready_launch.create_failure_queue(" not in source
    assert "managed_ready_runtime.create_failure_queue(" not in launch_source
    assert "create_ready_shell_failure_queue(" not in source
    assert "ReadyShellFailureQueue(" not in source
    assert "managed_ready_launch.schedule_startup_tasks(" in launch_source
    assert "managed_ready_runtime.schedule_startup_tasks(" not in launch_source
    assert "schedule_ready_shell_controller_startup_tasks(" not in source
    assert "schedule_ready_shell_startup_tasks(" not in source
    assert "managed_ready_launch.create_local_editor_warmup_adapter(" in launch_source
    assert (
        "managed_ready_runtime.create_local_editor_warmup_adapter(" not in launch_source
    )
    assert "create_ready_shell_local_editor_warmup_adapter(" not in source
    assert "ReadyShellLocalEditorWarmupAdapter(" not in source
    assert "managed_ready_launch.create_managed_startup_prelude(" in launch_source
    assert "managed_ready_runtime.create_managed_startup_prelude(" not in launch_source
    assert "create_ready_shell_managed_startup_prelude(" not in source
    assert "ReadyShellManagedStartupPrelude(" not in source
    assert "def launch_ready_shell" not in source
    assert "try_begin_ready_shell_launch(" not in source
    assert "launch_no_comfy_ready_shell(" not in source
    assert "publish_no_comfy_ready_shell_result(" not in source
    assert "StartupFailureController(" not in source
    assert "StartupFailClosedCleanupPortFactory(" not in source
    assert "GuiStartupTaskQueue(" not in source
    assert "start_local_editor_startup_warmup(" not in source
    assert (
        "startup_support_graph.startup_cancel_bridge.cancel_requested.connect"
        in shell_flow_source
    )
    assert (
        "startup_support_graph.startup_cancel_bridge.cancel_requested.emit"
        in shell_flow_source
    )
    assert "initial_splash_cancel_connector=initial_splash_cancel_connector" in source
    assert (
        "startup_splash_start_or_adopt=(\n"
        "            startup_support_graph.startup_splash_ports.start_or_adopt_launch_splash\n"
        "        )," in shell_flow_source
    )
    assert "initial_splash_cancel_connector(" not in source
    assert "start_or_adopt_launch_splash(" not in source
    assert "start_cutecanvas_sam_startup_warmup(" not in source
    assert "managed_ready_launch.create_target_activation_task(" in launch_source
    assert "managed_ready_runtime.create_target_activation_task(" not in launch_source
    assert "create_ready_shell_target_activation_task(" not in source
    assert "ReadyShellTargetActivationTask(" not in source
    assert "def activate_target_task" not in source
    assert "activate_ready_shell_target_task(" not in source
    assert "activate_ready_shell_target(" not in source
    assert "activation_result.started" not in source
    assert "activation_result.comfy_state" not in source
    assert 'with trace_span("activate_target_task.activate")' not in source
    assert (
        "managed_ready_launch.create_target_activation_task(\n"
        "            startup_cancelled=lambda: self.startup_cancellation_state.cancelled,"
        in launch_source
    )
    assert "mark_activation_started=" not in source
    assert "comfy_activation_started" not in source
    assert "managed_ready_launch.create_shell_build_task(" in launch_source
    assert "managed_ready_runtime.create_shell_build_task(" not in launch_source
    assert "create_ready_shell_build_task(" not in source
    assert "ReadyShellBuildTask(" not in source
    assert "def build_shell_task" not in source
    assert "build_ready_shell_skeleton_task(" not in source
    assert "build_ready_shell_skeleton(" not in source
    assert "built_shell_frame" not in source
    assert "managed_ready_launch.create_metadata_bridge_task(" in launch_source
    assert "managed_ready_runtime.create_metadata_bridge_task(" not in launch_source
    assert "create_ready_shell_metadata_bridge_task(" not in source
    assert "ReadyShellMetadataBridgeTask(" not in source
    assert "def wire_metadata_bridge_task" not in source
    assert "wire_ready_shell_metadata_bridge_task(" not in source
    assert "wire_ready_shell_metadata_bridge(" not in source
    assert "metadata_update_bridge = wire_ready_shell_metadata_bridge" not in source
    assert "managed_ready_launch.create_minimum_ready_task(" in launch_source
    assert "managed_ready_runtime.create_minimum_ready_task(" not in launch_source
    assert "create_ready_shell_minimum_ready_task(" not in source
    assert "ReadyShellMinimumReadyTask(" not in source
    assert "def mark_minimum_shell_ready_task" not in source
    assert "mark_ready_shell_minimum_ready_task(" not in source
    assert "            state=ready_state," not in source
    assert "mark_ready=lambda: setattr(" not in source
    assert "mark_ready_shell_minimum_ready(" not in source
    assert "managed_ready_launch.create_prompt_editor_warmup_task(" in launch_source
    assert (
        "managed_ready_runtime.create_prompt_editor_warmup_task(" not in launch_source
    )
    assert "create_ready_shell_prompt_editor_warmup_task(" not in source
    assert "ReadyShellPromptEditorWarmupTask(" not in source
    assert "def warm_prompt_editor_gui_task" not in source
    assert "warm_ready_shell_prompt_editor_gui(" not in source
    assert "warm_prompt_editor_gui_before_reveal(" not in source
    assert (
        "managed_ready_launch.create_initial_workspace_prehydration_task("
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_initial_workspace_prehydration_task("
        not in launch_source
    )
    assert "create_ready_shell_initial_workspace_prehydration_task(" not in source
    assert "ReadyShellInitialWorkspacePrehydrationTask(" not in source
    assert "def prehydrate_initial_workspace_task" not in source
    assert "prehydrate_ready_shell_initial_workspace_task(" not in source
    assert " prehydrate_ready_shell_initial_workspace(" not in source
    assert "ready_state.prehydration_attempted = True" not in source
    assert "prehydration_result.attempted" not in source
    assert "prehydrate_initial_workspace_before_show(" not in source
    assert "managed_ready_launch.create_post_show_controller(" in launch_source
    assert "managed_ready_runtime.create_post_show_controller(" not in launch_source
    assert "create_bound_ready_shell_post_show_controller(" not in source
    assert "create_ready_shell_post_show_controller(" not in source
    assert "ReadyShellPostShowController(" not in source
    assert (
        "backend_state_updater = managed_ready_state.backend_state_updater"
        not in source
    )
    assert "set_backend_state=backend_state_updater.update" not in source
    assert "update_backend_state=backend_state_updater.update" not in source
    assert "backend_state_updater=backend_state_updater" not in source
    assert "backend_state_updater.bind(" not in source
    assert "ReadyShellBackendStateUpdater(" not in source
    assert "def set_ready_shell_backend_state" not in source
    assert "project_ready_shell_backend_state(" not in source
    assert "update_built_shell_backend_state(" not in source
    assert "schedule_ready_shell_post_show_hydration(" not in source
    assert "schedule_post_show_hydration_after_reveal(" not in source
    assert " hydrate_ready_shell_initial_workspace(" not in source
    assert "hydrate_initial_workspace_after_show(" not in source
    assert "emit_ready_shell_visible_startup_summary(" not in source
    assert "emit_visible_startup_summary(" not in source
    assert "managed_ready_launch.create_show_gate_task(" in launch_source
    assert "managed_ready_runtime.create_show_gate_task(" not in launch_source
    assert "create_ready_shell_show_gate_task(" not in source
    assert "ReadyShellShowGateTask(" not in source
    assert "def try_show_main_window" not in source
    assert "try_reveal_ready_shell(" not in source
    assert "main_window_shown=ready_state.main_window_shown" not in source
    assert "mark_main_window_shown=lambda: setattr(" not in source
    assert "hydration_started=lambda: ready_state.hydration_started" not in source
    assert "mark_hydration_started=lambda: setattr(" not in source
    assert "prepare_ready_shell_hidden_restore_runtime(" not in source
    assert "prepare_hidden_restore_runtime_before_show(" not in source
    assert "warm_ready_shell_restored_cube_definitions(" not in source
    assert "shell_restore_warmup_controller" not in source
    assert "warm_restored_workspace_cube_definitions(" not in source
    assert "start_ready_shell_pre_show_restore_projection(" not in source
    assert "start_pre_show_restore_projection_if_available(" not in source
    assert '"main_shell.try_show.enter"' not in source
    assert '"main_shell.try_show.blocked"' not in source
    assert '"post_comfy.restore_priority.begin"' not in source
    assert "restore_projection_controller" not in source
    assert (
        "managed_ready_launch.create_startup_diagnostics_update_adapter"
        in launch_source
    )
    assert (
        "managed_ready_runtime.create_startup_diagnostics_update_adapter"
        not in launch_source
    )
    assert "create_ready_shell_startup_diagnostics_update_adapter(" not in source
    assert "ReadyShellStartupDiagnosticsUpdateAdapter(" not in source
    assert "request_ready_shell_startup_diagnostics_update(" not in source
    assert '"post_show.diagnostics.async_requested"' not in source
    assert "managed_ready_launch.create_reveal_task(" in launch_source
    assert "managed_ready_runtime.create_reveal_task(" not in launch_source
    assert "create_ready_shell_reveal_task(" not in source
    assert "ReadyShellRevealTask(" not in source
    assert "def reveal_main_window" not in source
    assert "connect_ready_shell_restore_finalized_warmups(" not in source
    assert "connect_restore_finalized_warmups(" not in source
    assert "schedule_nonessential_startup_warmups(" not in source
    assert "reveal_ready_shell_main_window(" not in source
    assert 'with trace_span("launch_splash.close")' not in source
    assert 'with trace_span("main_shell.show")' not in source
    assert '"Main shell revealed"' not in source
    assert "wire_model_metadata_update_bridge(" not in source
    assert 'splash.append_log("Preparing the application interface.")' not in source
    assert 'with trace_span("build_shell_task.build_main_window")' not in source
    assert "attach_restore_asset_preload_to_shell(" not in source


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
